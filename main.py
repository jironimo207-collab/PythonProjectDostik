import os
import re
import httpx
import uvicorn
from fastapi import FastAPI, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Импортируем инструменты для ограничения частоты запросов (Rate Limiting)
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import init_db, get_db
from models import Beer, Order  # Импортируем и Beer, и Order

# Создаём необходимые папки
os.makedirs("static/images", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Инициализация базы данных
init_db()

# 1. Инициализируем лимитер, определяющий пользователя по его IP-адресу
limiter = Limiter(key_func=get_remote_address)

# Создаём приложение
app = FastAPI(title="DOCTIC")

# 2. Привязываем лимитер к состоянию приложения FastAPI
app.state.limiter = limiter

# Загружаем переменные окружения.
load_dotenv()

# Приводим к единым именам, которые лежат в файле .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID")

# Отладочный принт в консоль при старте сервера
print("\n" + "=" * 40)
print(f"DEBUG ТГ-БОТА:\nТокен: {TELEGRAM_TOKEN}\nЧат ID: {YOUR_CHAT_ID}")
print("=" * 40 + "\n")

# Раздача статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключение шаблонов
templates = Jinja2Templates(directory="templates")


# Кастомный обработчик ошибок лимитера, чтобы фронтенд получал красивый текст вместо стандартной ошибки
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Слишком много запросов! Пожалуйста, подождите немного перед созданием нового предзаказа."}
    )


# Главная страница
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    beers = db.query(Beer).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"items": beers}  # В шаблоне карточки будут доступны через {{ items }}
    )


# Проверка сервера
@app.get("/health")
def health():
    return {"status": "ok"}


async def send_tg_notification(name: str, phone: str, email: str, item: str):
    """Функция отправки мгновенного уведомления в ваш Telegram-бот"""
    text = (
        f"🚨 **НОВЫЙ ПРЕДЗАКАЗ!**\n\n"
        f"👤 **Имя:** {name}\n"
        f"📞 **Телефон:** {phone}\n"
        f"📧 **Email:** {email if email else 'Не указан'}\n"
        f"📦 **Товар:** {item}\n\n"
        f"🧑‍💻 Срочно перезвоните клиенту для уточнения деталей!"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json={
                "chat_id": YOUR_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            })
            if response.status_code != 200:
                print(f"Ошибка Telegram API: {response.text}")
        except Exception as e:
            print(f"Ошибка при отправке запроса в Telegram: {e}")


# Обработка предзаказа с валидацией и ограничением запросов
@app.post("/submit-order")
@limiter.limit("2/minute")  # Защита от флуда: не более 2 запросов в минуту с одного IP
async def handle_order(
        request: Request,  # Обязательный параметр для работы slowapi!
        item_name: str = Form(...),
        username: str = Form(...),
        phone: str = Form(...),
        email: str = Form(None),
        db: Session = Depends(get_db)
):
    # Защита от взлома полей формы: проверяем, существует ли товар в каталоге
    beer_exists = db.query(Beer).filter(Beer.name == item_name).first()
    if not beer_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Указанный товар не существует в каталоге магазина."
        )

    # Валидация телефона: удаляем пробелы, скобки, дефисы и плюсы, оставляя только чистые цифры
    clean_phone = re.sub(r'[\s()+-]', '', phone)
    # Проверяем, что в номере остались только цифры и их количество находится в пределах от 10 до 15
    if not clean_phone.isdigit() or not (10 <= len(clean_phone) <= 15):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный формат номера телефона. Пожалуйста, введите реальный номер."
        )

    clean_username = username.strip()
    # Проверяем длину имени (от 2 до 30 символов)
    if not (2 <= len(clean_username) <= 30):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный формат имени. Пожалуйста, введите реальное имя (от 2 до 30 символов)."
        )

    # 1. Сохраняем в локальную базу данных SQLite очищенные данные
    new_order = Order(
        customer_name=clean_username,
        customer_phone=phone,
        customer_email=email,
        item_name=item_name
    )
    db.add(new_order)
    db.commit()

    # 2. Отправляем уведомление в ваш Telegram
    await send_tg_notification(name=clean_username, phone=phone, email=email, item=item_name)

    # 3. Возвращаем плоский статус успеха, который обработает JavaScript на фронтенде
    return {"status": "success"}


if __name__ == "__main__":
    # Запускаем приложение на порту 8000, чтобы избежать конфликтов прав sudo в Linux/WSL
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
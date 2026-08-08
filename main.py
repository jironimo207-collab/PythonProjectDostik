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

# 1. ЗАГРУЖАЕМ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ САМЫМ ПЕРВЫМ ДЕЛОМ!
# Это гарантирует, что все последующие импорты и модули увидят конфигурацию .env
load_dotenv()

# Импортируем инструменты для ограничения частоты запросов (Rate Limiting)
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Импортируем локальные инструменты работы с базой данных и модели
from database import init_db, get_db
from models import Beer, Order

# Создаём необходимые папки для работы приложения
os.makedirs("static/images", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Инициализация структуры базы данных
init_db()

# Инициализируем лимитер, определяющий уникальность пользователя по его IP-адресу
limiter = Limiter(key_func=get_remote_address)

# Создаём приложение FastAPI
app = FastAPI(title="DOCTIC")

# Привязываем лимитер к состоянию приложения FastAPI
app.state.limiter = limiter

# Достаем переменные, которые лежат в файле .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID")

# Отладочный принт в консоль для проверки успешности чтения .env
print("\n" + "=" * 40)
print(f"DEBUG ТГ-БОТА:\nТокен: {TELEGRAM_TOKEN}\nЧат ID: {YOUR_CHAT_ID}")
print("=" * 40 + "\n")

# Раздача статических файлов (картинок, стилей)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключение шаблонов Jinja2
templates = Jinja2Templates(directory="templates")


# Кастомный обработчик ошибок лимитера, чтобы фронтенд получал красивый текст вместо стандартной JSON ошибки
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Слишком много запросов! Пожалуйста, подождите немного перед созданием нового предзаказа."}
    )


# Главная страница (Каталог товаров)
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    beers = db.query(Beer).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"items": beers}  # Карточки пива передаются в шаблон в переменную items
    )


# Проверка жизнеспособности сервера
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


# Обработка предзаказа с валидацией, сохранением в БД и отправкой в ТГ
@app.post("/submit-order")
@limiter.limit("10/minute")  # Лимит увеличен до 10 в минуту для комфортного тестирования администратором
async def handle_order(
        request: Request,  # Обязательный параметр для корректной работы slowapi!
        item_name: str = Form(...),
        username: str = Form(...),
        phone: str = Form(...),
        email: str = Form(None),
        db: Session = Depends(get_db)
):
    # ИСПРАВЛЕНО: Проверяем существование товара по полю Beer.title, так как поля .name не существует в модели
    beer_exists = db.query(Beer).filter(Beer.title == item_name).first()
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

    # 1. Сохраняем в локальную базу данных SQLite очищенные данные о заказе
    new_order = Order(
        customer_name=clean_username,
        customer_phone=phone,
        customer_email=email,
        item_name=item_name
    )
    db.add(new_order)
    db.commit()

    # 2. Отправляем асинхронное уведомление в Telegram-бот администратора
    await send_tg_notification(name=clean_username, phone=phone, email=email, item=item_name)

    # 3. Возвращаем JSON-статус успеха, который корректно обработает JavaScript (fetch) на фронтенде
    return {"status": "success"}


if __name__ == "__main__":
    # Запускаем приложение uvicorn на порту 8000 с автоперезагрузкой при изменении файлов
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
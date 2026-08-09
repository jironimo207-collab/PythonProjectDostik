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
from zoneinfo import ZoneInfo
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
from datetime import datetime, time
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
templates = Jinja2Templates(directory=".")


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

async def send_tg_notification(name: str, phone: str, email: str, item: str, volume: float, total_price: float):
    """Функция отправки мгновенного уведомления в ваш Telegram-бот"""
    text = (
        f"🚨 **НОВЫЙ ПРЕДЗАКАЗ!**\n\n"
        f"👤 **Имя:** {name}\n"
        f"📞 **Телефон:** {phone}\n"
        f"📧 **Email:** {email if email else 'Не указан'}\n"
        f"🍺 **Товар:** {item}\n"
        f"📏 **Объём:** {volume} л\n"
        f"💰 **Итого к оплате:** {total_price} тг\n\n"
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


@app.post("/submit-order")
@limiter.limit("10/minute")
async def handle_order(
        request: Request,
        item_name: str = Form(...),
        username: str = Form(...),
        phone: str = Form(...),
        email: str = Form(None),
        volume: float = Form(1.0),            # <-- Новый параметр
        total_price: float = Form(0.0),       # <-- Новый параметр
        db: Session = Depends(get_db)
):
    current_time = datetime.now().time()

    start_time = time(9, 0)  # 09:00
    end_time = time(22, 30)  # 22:30

    if not (start_time <= current_time <= end_time):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Предзаказы принимаются только с 9:00 до 22:30. Пожалуйста, оформите заказ в рабочее время!"
        )
    beer_exists = db.query(Beer).filter(Beer.title == item_name).first()
    if not beer_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Указанный товар не существует в каталоге магазина."
        )

    clean_phone = re.sub(r'[\s()+-]', '', phone)
    if not clean_phone.isdigit() or not (10 <= len(clean_phone) <= 15):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный формат номера телефона."
        )

    clean_username = username.strip()
    if not (2 <= len(clean_username) <= 30):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный формат имени (от 2 до 30 символов)."
        )

    # Сохраняем в базу данных
    new_order = Order(
        customer_name=clean_username,
        customer_phone=phone,
        customer_email=email,
        item_name=item_name,
        volume=volume,
        total_price=total_price
    )
    db.add(new_order)
    db.commit()

    # Отправляем в Telegram
    await send_tg_notification(
        name=clean_username,
        phone=phone,
        email=email,
        item=item_name,
        volume=volume,
        total_price=total_price
    )

    return {"status": "success"}

if __name__ == "__main__":
    # Запускаем приложение uvicorn на порту 8000 с автоперезагрузкой при изменении файлов
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
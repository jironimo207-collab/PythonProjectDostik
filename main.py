import os
import re
import httpx
import uvicorn
from fastapi import FastAPI, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import init_db, get_db
from models import Beer, Order  # Импортируем и Beer, и Order

# Создаём необходимые папки
os.makedirs("static/images", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Инициализация базы данных
init_db()

# Создаём приложение
app = FastAPI(title="DOCTIC")

# Загружаем переменные окружения.
# Если запускаешь через WSL, можно явно указать путь: load_dotenv(dotenv_path="/mnt/c/Users/user/PycharmProjects/PivoMagazinDoctic/.env")
load_dotenv()

# Приводим к единым именам, которые лежат в файле .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID")

# Отладочный принт в консоль при старте сервера
print("\n" + "="*40)
print(f"DEBUG ТГ-БОТА:\nТокен: {TELEGRAM_TOKEN}\nЧат ID: {YOUR_CHAT_ID}")
print("="*40 + "\n")

# Раздача статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключение шаблонов
templates = Jinja2Templates(directory="templates")


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


# Обработка предзаказа с валидацией
@app.post("/submit-order")
async def handle_order(
        item_name: str = Form(...),
        username: str = Form(...),
        phone: str = Form(...),
        email: str = Form(None),
        db: Session = Depends(get_db)
):
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
    # 1. Сохраняем в локальную базу данных SQLite
    new_order = Order(
        customer_name=username,
        customer_phone=phone,
        customer_email=email,
        item_name=item_name
    )
    db.add(new_order)
    db.commit()

    # 2. Отправляем уведомление в ваш Telegram
    await send_tg_notification(name=username, phone=phone, email=email, item=item_name)

    # 3. Возвращаем плоский статус успеха, который обработает JavaScript на фронтенде
    return {"status": "success"}


if __name__ == "__main__":
    # Для работы через ngrok в WSL запускаем на порту 80
    uvicorn.run("main:app", host="0.0.0.0", port=80, reload=True)
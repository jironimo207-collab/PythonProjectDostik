from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from database import init_db, get_db
from models import Beer


# Создаём необходимые папки
os.makedirs("static/images", exist_ok=True)
os.makedirs("templates", exist_ok=True)


# Инициализация базы
init_db()


# Создаём приложение
app = FastAPI(
    title="DOCTIC"
)


# Раздача статических файлов
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# Подключение шаблонов
templates = Jinja2Templates(
    directory="templates"
)


# Главная страница
@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db)
):
    beers = db.query(Beer).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "items": beers
        }
    )


# Проверка сервера
@app.get("/health")
def health():
    return {
        "status": "ok"
    }
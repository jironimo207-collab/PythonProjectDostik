import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./beer_shop.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def init_db():
    from models import Base, Beer

    Base.metadata.create_all(bind=engine)
    image_dir = "static/images"
    os.makedirs(image_dir, exist_ok=True)
    db = SessionLocal()
    try:
        if db.query(Beer).count() == 0:
            files = os.listdir(image_dir)
            goods = [
                Beer(
                    title="Erzman",
                    price=1220,
                    description="светлое пиво",
                    image="/static/images.webp",
                    category="light"
                ),
                Beer(
                    title="Жигулёвское",
                    price=1130,
                    description="Классическое светлое пиво.",
                    image="/static/images.webp",
                    category="dark"
                ),
                Beer(
                    title="СССР",
                    price=1190,
                    description="Плотный вкус, ностальгический рецепт.",
                    image="/static/images.webp",
                    category="light"
                ),
                Beer(
                    title="Мягкое(Arasan)",
                    price=1130,
                    description="Классическое светлое пиво.",
                    image="/static/images.webp",
                    category="light"
                ),
                Beer(
                    title="Грушевый",
                    price=760,
                    description="Безалкогольный газированный напиток.",
                    image="/static/grucha.jpg",
                    category="drink"
                ),

                Beer(
                    title="Мохито",
                    price=760,
                    description="Идеальный прохладительный напиток для жаркой погоды.",
                    image="/static/moxito.jpg",
                    category="drink"
                ),

                Beer(
                    title="квас",
                    price=750,
                    description="Классический тёмный квас для жаркого дня.",
                    image="/static/kvas.jpg",
                    category="drink"
                )
            ]

            db.add_all(goods)
            db.commit()
            print("База заполнена")

    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db

    finally:
        db.close()
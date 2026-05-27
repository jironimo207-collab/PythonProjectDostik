from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Beer(Base):
    __tablename__ = "beers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)        # Для {{ item.title }}
    price = Column(Float, nullable=False)                     # Для {{ item.price }}
    description = Column(String, nullable=True)               # Для {{ item.description }}
    image = Column(String, nullable=True)
    category = Column(String, nullable=False)
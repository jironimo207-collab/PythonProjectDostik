from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Beer(Base):
    __tablename__ = "beers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)        # Для {{ item.title }}
    price = Column(Float, nullable=False)                     # Для {{ item.price }}
    description = Column(String, nullable=True)               # Для {{ item.description }}
    image = Column(String, nullable=True)
    category = Column(String, nullable=False)
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    customer_email = Column(String, nullable=True)
    item_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
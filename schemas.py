from pydantic import BaseModel
from typing import Optional

# Базовая схема
class BeerBase(BaseModel):
    title: str                     # Было: name
    price: float
    description: Optional[str] = None
    image: Optional[str] = None    # Было: image_path

# Схема для создания
class BeerCreate(BeerBase):
    pass

# Схема для ответа
class BeerResponse(BeerBase):
    id: int

    class Config:
        from_attributes = True
from decimal import Decimal
from pydantic import BaseModel
from typing import List
from datetime import datetime


class OrderMovieSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class OrderItemSchema(BaseModel):
    movie: OrderMovieSchema
    price_at_order: Decimal

    model_config = {"from_attributes": True}



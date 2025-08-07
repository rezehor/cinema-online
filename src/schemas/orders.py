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


class OrderSchema(BaseModel):
    id: int
    created_at: datetime
    status: str
    total_amount: Decimal
    order_items: List[OrderItemSchema]

    model_config = {"from_attributes": True}


class OrdersResponseSchema(BaseModel):
    orders: List[OrderSchema]


class AdminOrderSchema(BaseModel):
    id: int
    user_id: int
    status: str
    total_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}

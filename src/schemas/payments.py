from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from models import PaymentStatusEnum


class PaymentSchema(BaseModel):
    id: int
    amount: Decimal
    status: PaymentStatusEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminPaymentSchema(PaymentSchema):
    user_id: int

    model_config = {"from_attributes": True}

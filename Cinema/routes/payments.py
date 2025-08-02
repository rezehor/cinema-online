from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Cinema.config.dependencies import get_current_user
from Cinema.database import get_db
from Cinema.models import User, Payment, PaymentStatusEnum
from Cinema.schemas.payments import PaymentSchema, AdminPaymentSchema

router = APIRouter()

@router.get("/", response_model=List[PaymentSchema])
async def get_payment_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    result = await db.execute(stmt)
    payments = result.scalars().all()
    return payments




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


@router.get(
    "/admin/",
    response_model=List[AdminPaymentSchema],
    summary="Get all payments for admin",
)
async def list_all_payments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_id: Optional[int] = Query(None),
    status: Optional[PaymentStatusEnum] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    if current_user.group.name != "admin":
        raise HTTPException(status_code=403, detail="Only admins can see payments")

    stmt = select(Payment).order_by(Payment.created_at.desc())

    if user_id:
        stmt = stmt.where(Payment.user_id == user_id)
    if status:
        stmt = stmt.where(Payment.status == status)
    if start_date:
        stmt = stmt.where(Payment.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Payment.created_at <= end_date)

    result = await db.execute(stmt)
    return result.scalars().all()

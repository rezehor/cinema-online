import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import stripe
from fastapi import Depends, status, APIRouter, HTTPException, Header, Request, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from starlette.responses import JSONResponse
from Cinema.config.dependencies import get_current_user, get_accounts_email_notificator
from Cinema.config.settings import settings
from Cinema.database import get_db
from Cinema.models import Cart, CartItem, Order, OrderStatusEnum, OrderItem, Payment, PaymentStatusEnum, User
from Cinema.notifications.interfaces import EmailSenderInterface
from Cinema.schemas.orders import OrderSchema, OrdersResponseSchema, AdminOrderSchema

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)
async def place_order(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = await db.scalar(
        select(Cart)
        .options(selectinload(Cart.cart_items).joinedload(CartItem.movie))
        .where(Cart.user_id == current_user.id)
    )

    if not cart or not cart.cart_items:
        raise HTTPException(status_code=400, detail="Your cart is empty.")

    cart_items = cart.cart_items
    movie_ids = [item.movie_id for item in cart_items]

    purchased_stmt = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            Order.user_id == current_user.id,
            Order.status == OrderStatusEnum.PAID,
            OrderItem.movie_id.in_(movie_ids)
        )
    )
    purchased_ids = set((await db.execute(purchased_stmt)).scalars().all())

    pending_stmt = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            Order.user_id == current_user.id,
            Order.status == OrderStatusEnum.PENDING,
            OrderItem.movie_id.in_(movie_ids)
        )
    )
    pending_ids = set((await db.execute(pending_stmt)).scalars().all())

    valid_items = []
    total = Decimal("0.00")

    for item in cart_items:
        if item.movie_id in purchased_ids:
            continue
        if item.movie_id in pending_ids:
            continue
        if not item.movie.is_available:
            continue

        valid_items.append(item)
        total += item.movie.price

    if not valid_items:
        raise HTTPException(status_code=400, detail="No available items to order.")

    order = Order(
        user_id=current_user.id,
        status=OrderStatusEnum.PENDING,
        total_amount=total
    )
    db.add(order)
    await db.flush()

    for item in valid_items:
        db.add(OrderItem(
            order_id=order.id,
            movie_id=item.movie.id,
            price_at_order=item.movie.price
        ))

    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    order_with_items = await db.scalar(
        select(Order)
        .options(selectinload(Order.order_items).joinedload(OrderItem.movie))
        .where(Order.id == order.id)
    )

    return order_with_items


@router.get(
    "/orders/",
    response_model=OrdersResponseSchema,
    summary="Get all orders of current user"
)
async def get_user_orders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(
            selectinload(Order.order_items).joinedload(OrderItem.movie)
        )
        .order_by(Order.created_at.desc())
    )

    orders = result.scalars().all()

    return OrdersResponseSchema(
        orders=[OrderSchema.model_validate(order) for order in orders]
    )


@router.post(
    "/orders/{order_id}/pay",
    summary="Redirect to Stripe Checkout"
)
async def initiate_payment(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    stmt = (
        select(Order)
        .options(selectinload(Order.order_items).joinedload(OrderItem.movie))
        .where(Order.id == order_id, Order.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    order = result.scalars().first()

    total = sum(item.price_at_order for item in order.order_items)
    if order.total_amount != total:
        raise HTTPException(status_code=400, detail="Invalid order total amount.")

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Order is not pending")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    line_items = [
        {
            "price_data": {
                "currency": "usd",
                "product_data": {"name": item.movie.name},
                "unit_amount": int(item.price_at_order * 100),
            },
            "quantity": 1,
        }
        for item in order.order_items
    ]

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=f"{settings.FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/payment-cancel",
            metadata={"order_id": str(order.id), "user_id": str(current_user.id)},
        )
        return {"payment_url": session.url}
    except stripe.error.CardError as e:
        raise HTTPException(status_code=400, detail="Card declined. Try another method.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


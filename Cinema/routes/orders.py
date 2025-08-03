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
from Cinema.models import (
    Cart,
    CartItem,
    Order,
    OrderStatusEnum,
    OrderItem,
    Payment,
    PaymentStatusEnum,
    User,
)
from Cinema.notifications.interfaces import EmailSenderInterface
from Cinema.schemas.orders import OrderSchema, OrdersResponseSchema, AdminOrderSchema

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=OrderSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order from the cart",
    description="Creates a new order with a 'pending' status from the items in the user's cart. The cart is cleared upon successful order creation.",
)
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
            OrderItem.movie_id.in_(movie_ids),
        )
    )
    purchased_ids = set((await db.execute(purchased_stmt)).scalars().all())

    pending_stmt = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            Order.user_id == current_user.id,
            Order.status == OrderStatusEnum.PENDING,
            OrderItem.movie_id.in_(movie_ids),
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
        user_id=current_user.id, status=OrderStatusEnum.PENDING, total_amount=total
    )
    db.add(order)
    await db.flush()

    for item in valid_items:
        db.add(
            OrderItem(
                order_id=order.id,
                movie_id=item.movie.id,
                price_at_order=item.movie.price,
            )
        )

    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    order_with_items = await db.scalar(
        select(Order)
        .options(selectinload(Order.order_items).joinedload(OrderItem.movie))
        .where(Order.id == order.id)
    )

    return order_with_items


@router.get(
    "/",
    response_model=OrdersResponseSchema,
    summary="Get the user's order history",
    description="Retrieves a list of all past and present orders for the currently authenticated user.",
)
async def get_user_orders(
    db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(selectinload(Order.order_items).joinedload(OrderItem.movie))
        .order_by(Order.created_at.desc())
    )

    orders = result.scalars().all()

    return OrdersResponseSchema(
        orders=[OrderSchema.model_validate(order) for order in orders]
    )


@router.post(
    "/{order_id}/pay",
    summary="Initiate payment for an order",
    description="Creates a payment session with an external provider (Stripe) and returns a URL for the user to be redirected to for payment."
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

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    total = sum(item.price_at_order for item in order.order_items)
    if order.total_amount != total:
        raise HTTPException(status_code=400, detail="Invalid order total amount.")

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
        raise HTTPException(
            status_code=400, detail="Card declined. Try another method."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.post(
    "/webhooks/stripe",
    summary="Stripe webhook handler (for server-to-server communication)",
    description="Receives events from Stripe to update the status of payments and orders. This endpoint is not intended to be called by users directly.",
    tags=["Webhooks"],
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning(f"Stripe webhook verification failed: {str(e)}")
        raise HTTPException(
            status_code=400, detail="Invalid Stripe signature or payload."
        )

    event_type = event.get("type")
    logger.info(f"Stripe event received: {event_type}")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            order_id = int(session["metadata"]["order_id"])
        except (KeyError, ValueError):
            logger.error("Missing or invalid order_id in session metadata.")
            raise HTTPException(status_code=400, detail="Invalid session metadata.")

        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.order_items).joinedload(OrderItem.movie),
                joinedload(Order.user),
            )
        )
        result = await db.execute(stmt)
        order = result.scalars().first()

        if not order:
            logger.warning(f"Order with ID {order_id} not found.")
            raise HTTPException(status_code=404, detail="Order not found.")

        if order.status != OrderStatusEnum.PENDING:
            logger.info(f"Order {order.id} already processed. Skipping.")
            return JSONResponse(
                status_code=status.HTTP_200_OK, content={"status": "already_processed"}
            )

        try:
            order.status = OrderStatusEnum.PAID

            payment = Payment(
                order_id=order.id,
                user_id=order.user_id,
                amount=Decimal(session["amount_total"]) / 100,
                status=PaymentStatusEnum.SUCCESSFUL,
                external_payment_id=session["payment_intent"],
            )

            db.add(payment)

            await email_sender.send_order_confirmation_email(
                email=order.user.email, order_id=order.id
            )

            await db.commit()
            logger.info(f"Order {order.id} marked as PAID and confirmation email sent.")

        except Exception as e:
            logger.exception(f"Failed to process payment for order {order_id}: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500, detail="Internal error while processing payment."
            )
    else:
        logger.info(f"Unhandled Stripe event type: {event_type}")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED, content={"status": "ignored"}
        )

    return {"status": "success"}


@router.post(
    "/orders/{order_id}/cancel",
    summary="Cancel a pending order",
    description="Allows a user to cancel an order that has a 'pending' status. Paid orders cannot be canceled via this endpoint."
)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = await db.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=400, detail="Only pending orders can be canceled"
        )

    order.status = OrderStatusEnum.CANCELED
    await db.commit()

    return {"detail": "Order canceled successfully"}


@router.post(
    "/orders/{order_id}/refund",
    summary="Request a refund for a paid order",
    description="Allows an authenticated user to request a refund for an order that has a 'PAID' status."
)
async def refund_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = await db.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != OrderStatusEnum.PAID:
        raise HTTPException(
            status_code=400, detail="Order is not paid or already refunded"
        )

    payment = (
        (
            await db.execute(
                select(Payment)
                .where(Payment.order_id == order.id)
                .order_by(Payment.created_at.desc())
            )
        )
        .scalars()
        .first()
    )

    if not payment or not payment.external_payment_id:
        raise HTTPException(status_code=400, detail="No Stripe payment found")

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY

        refund = stripe.Refund.create(payment_intent=payment.external_payment_id)

        order.status = OrderStatusEnum.REFUNDED
        payment.status = PaymentStatusEnum.REFUNDED
        await db.commit()

        return {"message": "Refund initiated successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refund failed: {str(e)}")


@router.get(
    "/admin/",
    response_model=List[AdminOrderSchema],
    summary="List and filter all user orders (Admin only)",
    description="Provides administrators with a comprehensive list of all user orders. The list can be filtered by user, date range, and order status.",
)
async def admin_get_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_id: Optional[int] = Query(None),
    status: Optional[OrderStatusEnum] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    if current_user.group.name != "admin":
        raise HTTPException(status_code=403, detail="Only admins can see orders.")

    stmt = select(Order).options(joinedload(Order.user))

    if user_id:
        stmt = stmt.where(Order.user_id == user_id)
    if status:
        stmt = stmt.where(Order.status == status)
    if start_date:
        stmt = stmt.where(Order.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Order.created_at <= end_date)

    stmt = stmt.order_by(Order.created_at.desc())

    result = await db.execute(stmt)
    return result.scalars().all()

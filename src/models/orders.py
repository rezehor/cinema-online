import enum

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum, DECIMAL, func
from sqlalchemy.orm import relationship

from models import Base


class OrderStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status = Column(
        Enum(OrderStatusEnum, name="orderstatusenum"), nullable=False, default=OrderStatusEnum.PENDING
    )
    total_amount = Column(DECIMAL(10, 2), nullable=True)

    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    price_at_order = Column(DECIMAL(10, 2), nullable=False)

    order = relationship("Order", back_populates="order_items")
    movie = relationship("Movie", back_populates="order_items")
    payment_items = relationship("PaymentItem", back_populates="order_item")

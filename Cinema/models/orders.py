import enum

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum, DECIMAL, func
from sqlalchemy.orm import relationship

from Cinema.models import Base


class StatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Enum(StatusEnum), nullable=False, default=StatusEnum.PENDING)
    total_amount = Column(DECIMAL(10,2), nullable=True)

    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")





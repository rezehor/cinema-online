import enum

from sqlalchemy import Column, Integer, ForeignKey, DateTime, func, Enum, DECIMAL, String
from sqlalchemy.orm import relationship

from Cinema.models import Base


class PaymentStatusEnum(str, enum.Enum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.SUCCESSFUL)
    amount = Column(DECIMAL(10,2), nullable=False)
    external_payment_id = Column(String, nullable=True)

    user = relationship("User", back_populates="payments")
    order = relationship("Order", back_populates="payments")
    payment_items = relationship("PaymentItem", back_populates="payment")




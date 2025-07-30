from sqlalchemy import Column, Integer, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship

from Cinema.models import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    user = relationship("User", back_populates="cart")

    cart_items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    cart = relationship("Cart", back_populates="cart_items")
    movie = relationship("Movie", back_populates="cart_items")

    __table_args__ = (
        UniqueConstraint("cart_id", "movie_id", name="unique_cart_item_constraint"),
    )

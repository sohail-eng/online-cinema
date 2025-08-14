from enum import Enum

from sqlalchemy.orm import relationship

from app.db.database import Base

from sqlalchemy import Column, Integer, ForeignKey, func, Enum as SqlEnum, TIMESTAMP, DECIMAL


class OrderStatusEnum(str, Enum):
    pending = "PENDING"
    paid = "PAID"
    canceled = "CANCELED"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status = Column(SqlEnum(OrderStatusEnum), default=OrderStatusEnum.pending)
    total_amount = Column(DECIMAL(10, 2))

    order_items = relationship("OrderItem", back_populates="order")
    user_profile = relationship("UserProfile", back_populates="order")
    payments = relationship("Payment", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    price_at_order = Column(DECIMAL(10, 2))

    order = relationship("Order", back_populates="order_items")
    movie = relationship("Movie", back_populates="order_items")
    payment_items = relationship("PaymentItem", back_populates="order_item")

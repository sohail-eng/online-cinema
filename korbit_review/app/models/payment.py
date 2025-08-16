from enum import Enum

from sqlalchemy.orm import relationship

from app.db.database import Base

from sqlalchemy import Column, Integer, ForeignKey, func, Enum as SqlEnum, TIMESTAMP, DECIMAL, String


class PaymentStatusEnum(str, Enum):
    successful = "SUCCESSFUL"
    canceled = "CANCELED"
    refunded = "REFUNDED"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status = Column(SqlEnum(PaymentStatusEnum), default=PaymentStatusEnum.successful)
    amount = Column(DECIMAL(10, 2))
    external_payment_id = Column(String(400))

    user_profile = relationship("UserProfile", back_populates="payments")
    order = relationship("Order", back_populates="payments")
    payment_items = relationship("PaymentItem", back_populates="payment")

    @property
    def count_of_items(self):
        return len(self.payment_items)


class PaymentItem(Base):
    __tablename__ = "payment_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    order_item_id = Column(Integer, ForeignKey("orders.id"), unique=True, nullable=False)
    price_at_payment = Column(DECIMAL(10, 2), nullable=False)

    payment = relationship("Payment", back_populates="payment_items")
    order_item = relationship("OrderItem", back_populates="payment_item")

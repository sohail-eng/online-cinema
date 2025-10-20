from sqlalchemy.orm import relationship

from app.db.database import Base

from sqlalchemy import Column, Integer, ForeignKey, func, UniqueConstraint, TIMESTAMP


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), unique=True)

    user_profile = relationship("UserProfile", back_populates="cart")
    cart_items = relationship("CartItem", back_populates="cart")

    @property
    def count_of_all_items_in_cart(self):
        return len(self.cart_items)


class CartItem(Base):
    __tablename__ = "cart_items"

    __table_args__ = (
        UniqueConstraint(
            "cart_id", "movie_id"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    added_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())

    cart = relationship("Cart", back_populates="cart_items")
    movie = relationship("Movie", back_populates="cart_items")

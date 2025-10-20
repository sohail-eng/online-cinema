from sqlalchemy.orm import relationship

from app.db.database import Base

from sqlalchemy import Column, Integer, ForeignKey, String, DateTime


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String(100), unique=True)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="activation_token")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String(300), unique=True)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="password_reset_token")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String(300), unique=True)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="refresh_token")


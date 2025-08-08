from enum import Enum

from sqlalchemy import Column, Integer, ForeignKey, String, Enum as SqlEnum, Boolean, DateTime, func, Date
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class UserGroupEnum(str, Enum):
    user = "USER"
    moderator = "MODERATOR"
    admin = "ADMIN"

class GenderEnum(str, Enum):
    man = "MAN"
    woman = "WOMAN"


class UserGroup(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(SqlEnum(UserGroupEnum), unique=True, nullable=False)

    users = relationship("User", back_populates="user_group")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(150), nullable=False)
    is_active = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    group_id = Column(Integer, ForeignKey("user_groups.id"))

    user_group = relationship("UserGroup", back_populates="users")
    user_profile = relationship("UserProfile", back_populates="user", uselist=False)
    activation_token = relationship("ActivationToken", back_populates="user", uselist=False)
    password_reset_token = relationship("PasswordResetToken", back_populates="user", uselist=False)
    refresh_token = relationship("RefreshToken", back_populates="user", uselist=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    first_name = Column(String(60), nullable=True)
    last_name = Column(String(60), nullable=True)
    avatar = Column(String(300), nullable=True)
    gender = GenderEnum
    date_of_birth = Column(Date, nullable=True)
    info = Column(String(200), nullable=True)

    user = relationship("User", back_populates="user_profile")


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

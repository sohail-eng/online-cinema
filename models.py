from enum import Enum

from pydantic import BaseModel
from sqlalchemy import Column, Integer, ForeignKey, String, Enum as SqlEnum, Boolean, DateTime, func, text
from sqlalchemy.orm import relationship


class UserGroupEnum(str, Enum):
    user = "USER"
    moderator = "MODERATOR"
    admin = "ADMIN"

class GenderEnum(str, Enum):
    man = "MAN"
    woman = "WOMAN"


class UserGroup(BaseModel):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(SqlEnum(UserGroupEnum), unique=True, nullable=False)

    users = relationship("User", back_populates="user_group")


class User(BaseModel):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(150), nullable=False)
    is_active = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    group_id = Column(Integer, ForeignKey("user_groups.id"))

    user_group = relationship("UserGroup", back_populates="users")

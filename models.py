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

from datetime import datetime, date
from enum import Enum
from typing import Optional

from pydantic import ConfigDict, BaseModel, EmailStr, Field


class UserGroup(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(
        from_attributes=True
    )


class UserBase(BaseModel):
    email: EmailStr


class UserCreated(UserBase):
    id: int
    group: UserGroup

    model_config = ConfigDict(
        from_attributes=True
    )


class UserRead(UserBase):
    id: int
    user_group: UserGroup

    model_config = ConfigDict(
        from_attributes=True
    )


class GenderEnum(str, Enum):
    man = "MAN"
    woman = "WOMAN"


class UserProfileRead(BaseModel):
    id: int
    user: UserRead
    first_name: Optional[str] = Field(max_length=60, default=None)
    last_name: Optional[str] = Field(max_length=60, default=None)
    avatar: Optional[str] = Field(max_length=300, default=None)
    gender: Optional[GenderEnum]
    date_of_birth: Optional[date] = None
    info: Optional[str] = Field(max_length=200)

    model_config = ConfigDict(
        from_attributes=True
    )

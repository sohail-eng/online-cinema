from typing import Optional

from pydantic import BaseModel, EmailStr


class TokenPayload(BaseModel):
    email: EmailStr


class LoginTokens(BaseModel):
    access_token: str
    header: Optional[str] = "bearer"


class AccessToken(BaseModel):
    access_token: str

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

class SendNewActivationTokenSchema(BaseModel):
    email: EmailStr

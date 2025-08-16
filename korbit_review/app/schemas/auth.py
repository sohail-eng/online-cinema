from typing import Optional

import pydantic
from pydantic import BaseModel, EmailStr, model_validator, field_validator


class TokenPayload(BaseModel):
    email: EmailStr


class LoginTokens(BaseModel):
    access_token: str
    header: Optional[str] = "bearer"


class AccessToken(BaseModel):
    access_token: str


class SendNewActivationTokenSchema(BaseModel):
    email: EmailStr


class ChangePasswordRequestSchema(BaseModel):
    email: EmailStr


class NewPasswordDataSchema(BaseModel):
    password1: str
    password2: str

    @model_validator(mode="after")
    def passwords_validate(self):
        password1 = self.password1
        password2 = self.password2

        if password1 != password2:
            raise pydantic.ValidationError("Passwords are not equal")

        if password1.isalpha() or password1.isnumeric() or len(password1) < 8:
            return pydantic.ValidationError(
                "Password must contain not only digits or numbers and must be longer than 8 characters")

        return self


class CreateUserForm(BaseModel):
    email: EmailStr
    password: str
    group_id: int

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str):
        if len(password) < 8 or password.isnumeric() or password.isalpha():
            raise pydantic.ValidationError("Password must contain at least 8 symbols, also not only digits or numbers.")
        return password

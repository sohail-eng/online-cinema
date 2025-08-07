from typing import Optional

from pydantic import BaseModel, EmailStr


class TokenPayload(BaseModel):
    email: EmailStr

class LoginTokens(BaseModel):
    access_token: str
    header: Optional[str] = "bearer"

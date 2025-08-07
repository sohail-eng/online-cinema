from datetime import timedelta, datetime, timezone

from fastapi import HTTPException, status
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.annotation import Annotated

import models
from settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_hashed_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(raw_password, hashed_password)


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_DURATION = settings.ACCESS_TOKEN_DURATION


def create_token(data: dict, type: str, expiration: timedelta) -> str:
    to_encode = data.copy()
    exp = datetime.now(timezone.utc) + expiration
    to_encode.update({"exp": exp, "type": type})
    token = jwt.encode(to_encode, key=SECRET_KEY, algorithm=ALGORITHM)
    return token

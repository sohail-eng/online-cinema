from datetime import timedelta, datetime, timezone

from fastapi import HTTPException, status
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.annotation import Annotated

import models
import schemas
from settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_hashed_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(raw_password, hashed_password)


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_DURATION = settings.ACCESS_TOKEN_DURATION


def create_token(data: dict, expiration: timedelta) -> str:
    to_encode = data.copy()
    exp = datetime.now(timezone.utc) + expiration
    to_encode.update({"exp": exp})
    token = jwt.encode(to_encode, key=SECRET_KEY, algorithm=ALGORITHM)
    return token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: "AsyncSession") -> models.User | None:
    invalid_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate token",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHM)
        email = payload.get("sub")
        token_type = payload.get("type")
        token_expire = payload.get("exp")

        if not payload or not email or not token_type:
            raise invalid_credentials_exception

        if token_expire < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your token is already expired")

        token_data = schemas.TokenPayload(email=email)
    except JWTError:
        raise invalid_credentials_exception

    from . import crud
    current_user = await crud.get_user_by_email(email=token_data.email, db=db)
    if not current_user:
        raise invalid_credentials_exception
    return current_user

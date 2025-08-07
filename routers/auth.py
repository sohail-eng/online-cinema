from datetime import timedelta, timezone, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import crud
import models
import schemas
import security
from models import RefreshToken
from schemas import AccessToken
from settings import settings
from crud import get_user_by_email
from database import get_db
from security import create_token, verify_password

router = APIRouter()

DpGetDB = Annotated[AsyncSession, Depends(get_db)]


@router.post("login/", response_model=schemas.LoginTokens)
async def login_endpoint(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DpGetDB, response: Response):
    email = form_data.username
    password = form_data.password
    user = await get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User by provided email was not fount...")
    password_check = verify_password(password, user.hashed_password)
    if not password_check:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password were provided")
    data = {
        "type": "access",
        "sub": user.email,
        "role": user.user_group
    }
    access_token = create_token(data=data, expiration=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    data.update({"type": "refresh"})
    refresh_expires_at = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_token(data=data, expiration=refresh_expires_at)

    refresh_token_obj = RefreshToken(
        user_id=user.id,
        expires_at=(datetime.now(timezone.utc) + refresh_expires_at),
        token=refresh_token
    )
    db.add(refresh_token_obj)
    await db.commit()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=True,  # HTTPS <------------------------------
        expires=refresh_token_obj.expires_at
    )

    return schemas.LoginTokens(
        access_token=access_token,
    )

async def validate_refresh_token(refresh_token: Annotated[str | None, Cookie()], db: DpGetDB):
    invalid_token_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Refresh Token was provided")

    if not refresh_token:
        raise invalid_token_exception

    result = await db.execute(select(models.RefreshToken).filter(models.RefreshToken.token == refresh_token))
    refresh_token_obj = result.scalar_one_or_none()
    if not refresh_token_obj:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token wasn't provided")
    try:
        payload = jwt.decode(token=refresh_token_obj.token, key=settings.SECRET_KEY, algorithms=settings.ALGORITHM)
        token_exp = payload.get("exp", "")
        token_type = payload.get("type", "")
        token_sub = payload.get("sub", "")

        if not token_exp or not token_type or not token_sub:
            raise invalid_token_exception

        if token_exp < datetime.now(timezone.utc) or token_type != "refresh":
            raise invalid_token_exception

    except JWTError:
        raise invalid_token_exception

    user = await crud.get_user_by_email(token_sub, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User from refresh token not exist")
    return user


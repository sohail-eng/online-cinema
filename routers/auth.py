from datetime import timedelta, timezone, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import schemas
from models import RefreshToken
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
        secure=True,
        expires=refresh_token_obj.expires_at
    )

    return schemas.LoginTokens(
        access_token=access_token,
    )
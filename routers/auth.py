import aiofiles

from datetime import timedelta, timezone, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import RedirectResponse, JSONResponse

import crud
import models
import schemas
import security
from email_service.email_sender import send_email, generate_activation_code
from models import RefreshToken, ActivationToken
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


@router.post("token/refresh/")
async def refresh_token_endpoint(user: Depends(validate_refresh_token)) -> AccessToken:
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Something went wrong. Try again.")

    data = {
        "type": "access",
        "sub": user.email,
        "role": user.user_group
    }
    new_access_token = create_token(data=data, expiration=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return schemas.AccessToken(access_token=new_access_token)


@router.post("register/", response_model=schemas.UserCreated)
async def register_user(db: DpGetDB, data: schemas.CreateUserForm):
    user = get_user_by_email(data.email, db)
    if user:
        raise AttributeError("User with provided email already exists.")
    result_group = await db.execute(select(models.UserGroup).filter(models.UserGroup.id == data.group_id))
    user_group = result_group.scalar_one_or_none()
    if not user_group:
        raise ValueError("Group by provided id does not exist")

    hashed_password = security.get_hashed_password(data.password)
    user_create = models.User(
        email=str(data.email),
        hashed_password=hashed_password,
        group_id=data.group_id
    )
    db.add(user_create)
    await db.commit()
    await db.refresh(user_create)

    activation_token = generate_activation_code()
    activation_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)

    activation_token_obj = ActivationToken(
        user_id=user_create.id,
        token=activation_token,
        expires_at=activation_code_expires_at
    )
    db.add(activation_token_obj)
    await db.commit()
    await db.refresh(activation_token_obj)

    activation_link = f"{settings.WEBSITE_URL}/activate/?token={activation_token_obj.token}"

    async with aiofiles.open("email_service/email_templates/register.html", "r") as f:
        register_html = await f.read()

    html = register_html.replace("{{ user_email }}", user_create.email).replace("{{ activation_link }}", activation_link)

    send_email(user_email=user_create.email, subject="Account Activation", html=html)
    return schemas.UserCreated(id=user_create.id, email=user_create.email, group=user_create.user_group)


@router.get("activate/{token}")
async def activate_account(db: DpGetDB, token: str):
    result_act_token = await db.execute(select(models.ActivationToken).filter(models.ActivationToken.token == token))
    activation_token_obj = result_act_token.scalar_one_or_none()

    if not activation_token_obj:
        raise AttributeError("Invalid activation token")

    if activation_token_obj.expires_at < datetime.now(timezone.utc):
        return RedirectResponse(f"{settings.WEBSITE_URL}/send_new_activation_token/")

    user = activation_token_obj.user
    user.is_active = True
    await db.delete(activation_token_obj)
    await db.commit()

    return JSONResponse(content={"detail": "You account was successfully activated!"}, status_code=status.HTTP_200_OK)


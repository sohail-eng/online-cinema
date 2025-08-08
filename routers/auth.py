import aiofiles

from datetime import timedelta, timezone, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, BackgroundTasks
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
from email_service.email_sender import send_email, generate_secret_code
from models import RefreshToken, ActivationToken, PasswordResetToken
from schemas import AccessToken, SendNewActivationTokenSchema
from settings import settings
from database import get_db
from security import create_token, verify_password, get_hashed_password

router = APIRouter()

DpGetDB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/login/", response_model=schemas.LoginTokens)
async def login_endpoint(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DpGetDB, response: Response):
    email = form_data.username
    password = form_data.password
    user = await security.get_user_by_email(email, db)
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
    invalid_token_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                            detail="Invalid Refresh Token was provided")

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


@router.post("/token/refresh/")
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


@router.post("/register/", response_model=schemas.UserCreated)
async def register_user_endpoint(db: DpGetDB, data: schemas.CreateUserForm, background_tasks: BackgroundTasks):
    user = await security.get_user_by_email(data.email, db)
    if user:
        raise HTTPException(status_code=409, detail="User with this email already exists.")
    result_group = await db.execute(select(models.UserGroup).filter(models.UserGroup.id == data.group_id))
    user_group = result_group.scalar_one_or_none()
    if not user_group:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group by provided id does not exist")

    hashed_password = security.get_hashed_password(data.password)
    user_create = models.User(
        email=str(data.email),
        hashed_password=hashed_password,
        group_id=data.group_id
    )
    db.add(user_create)
    await db.commit()
    await db.refresh(user_create)

    activation_token = generate_secret_code()
    activation_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)

    activation_token_obj = ActivationToken(
        user_id=user_create.id,
        token=activation_token,
        expires_at=activation_code_expires_at
    )
    db.add(activation_token_obj)
    await db.commit()
    await db.refresh(activation_token_obj)

    activation_link = f"{settings.WEBSITE_URL}/activate/{activation_token_obj.token}"

    async with aiofiles.open("email_service/email_templates/register.html", "r") as f:
        register_html = await f.read()

    html = register_html.replace("{{ user_email }}", user_create.email).replace("{{ activation_link }}",
                                                                                activation_link)

    background_tasks.add_task(
        send_email,
        user_email=user_create.email,
        subject="Account Activation",
        html=html
    )
    return schemas.UserCreated(id=user_create.id, email=user_create.email, group=user_create.user_group)


@router.get("/activate/{token}/")
async def activate_account_endpoint(db: DpGetDB, token: str):
    result_act_token = await db.execute(select(models.ActivationToken).filter(models.ActivationToken.token == token))
    activation_token_obj = result_act_token.scalar_one_or_none()

    if not activation_token_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid activation token")

    if activation_token_obj.expires_at < datetime.now(timezone.utc):
        return RedirectResponse(f"{settings.WEBSITE_URL}/send_new_activation_token/{activation_token_obj.token}")

    user = activation_token_obj.user
    user.is_active = True
    await db.delete(activation_token_obj)
    await db.commit()

    return JSONResponse(content={"detail": "You account was successfully activated!"}, status_code=status.HTTP_200_OK)


@router.post("/send_new_activation_token/{expired_token}/")
async def send_new_activation_token_endpoint(db: DpGetDB, expired_token: str, data: SendNewActivationTokenSchema,
                                             background_tasks: BackgroundTasks):
    result_act_token = await db.execute(
        select(models.ActivationToken).filter(models.ActivationToken.token == expired_token))
    expired_activation_token_obj = result_act_token.scalar_one_or_none()

    if not expired_activation_token_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid activation token")

    async with aiofiles.open("email_service/email_templates/register.html", "r") as f:
        html_text = await f.read()

    new_activate_token = generate_secret_code()
    if data.email != expired_activation_token_obj.user.email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Please enter your correct email. (Email which was just written isn't equal to your account email)")

    new_activation_token_expire = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)
    activation_token_new_obj = ActivationToken(
        user_id=expired_activation_token_obj.user.id,
        token=new_activate_token,
        expires_at=new_activation_token_expire
    )
    activation_link = f"{settings.WEBSITE_URL}/activate/{new_activate_token}"

    await db.delete(expired_activation_token_obj)
    db.add(activation_token_new_obj)
    await db.commit()
    await db.refresh(activation_token_new_obj)

    html = html_text.replace("{{ user_email }}", activation_token_new_obj.user.email).replace("{{ activation_link }}",
                                                                                              activation_link)
    background_tasks.add_task(
        send_email,
        user_email=activation_token_new_obj.user.email,
        subject="New Activation Token",
        html=html
    )

    return JSONResponse(content={"detail": "Just was sent new activation code"}, status_code=status.HTTP_200_OK)


@router.get("/logout/")
async def logout_endpoint(db: DpGetDB, user: Depends(validate_refresh_token)):
    result_refresh_token_to_delete = await db.execute(
        select(models.RefreshToken).filter(models.RefreshToken.token == user.refresh_token.token))
    refresh_token_to_delete = result_refresh_token_to_delete.scalar_one_or_none()
    if not refresh_token_to_delete:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Something went wrong during getting refresh token")

    await db.delete(refresh_token_to_delete)
    await db.commit()

    response = JSONResponse(content={"detail": "Successfully logged out"})
    response.delete_cookie("refresh_token")
    return response


@router.post("/change_password/")
async def change_password_response_endpoint(db: DpGetDB, data: schemas.ChangePasswordRequestSchema,
                                            background_tasks: BackgroundTasks):
    user = await security.get_user_by_email(email=data.email, db=db)

    if not user:
        return JSONResponse(content={"detail": "We sent a Reset Code if account by provided email exists"},
                            status_code=status.HTTP_200_OK)

    async with aiofiles.open("email_service/email_templates/change_password.html", "r") as f:
        html_template = await f.read()

    reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)

    reset_token = generate_secret_code(length=40)
    reset_token_obj = PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=reset_expires_at
    )
    db.add(reset_token_obj)
    await db.commit()

    change_password_link = f"{settings.WEBSITE_URL}/change_password/{reset_token}"
    html = html_template.replace("{{ user_email }}", user.email).replace("{{ change_password_link }}",
                                                                         change_password_link)

    background_tasks.add_task(
        send_email,
        user_email=user.email,
        subject="Reset Password Code",
        html=html
    )

    return JSONResponse(content={"detail": "We sent a Reset Code if account by provided email exists"},
                        status_code=status.HTTP_200_OK)


@router.post("/change_password/{change_password_token}/")
async def change_password_endpoint(db: DpGetDB, change_password_token: str,
                                   new_password_data: schemas.NewPasswordDataSchema):
    result_reset_code = await db.execute(
        select(models.PasswordResetToken).filter(models.PasswordResetToken.token == change_password_token))
    reset_code_obj = result_reset_code.scalar_one_or_none()

    if not reset_code_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reset code was not found.")

    if reset_code_obj.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reset code is already expired")

    user = await security.get_user_by_email(email=reset_code_obj.user.email, db=db)

    hashed_password = get_hashed_password(new_password_data.passoword1)

    user.hashed_password = hashed_password
    await db.delete(reset_code_obj)
    await db.commit()

    return JSONResponse(content={"detail": "Successfully changed password"}, status_code=status.HTTP_200_OK)

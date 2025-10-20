import aiofiles

from datetime import timedelta, timezone, datetime
from typing import Annotated

from fastapi import HTTPException, BackgroundTasks
from fastapi.params import Cookie
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.core.security import verify_password, create_token, get_hashed_password
from app.core.settings import settings
from app.crud.user import get_user_by_email
from app.models.auth import RefreshToken, ActivationToken, PasswordResetToken
from app.models.user import User, UserGroup, UserProfile
from app.schemas.auth import CreateUserForm, SendNewActivationTokenSchema, ChangePasswordRequestSchema, \
    NewPasswordDataSchema
from app.services.email_service.email_sender import generate_secret_code, send_email
from app.utils.dependencies import DpGetDB


async def validate_refresh_token(refresh_token: Annotated[str | None, Cookie()], db: DpGetDB) -> User:
    invalid_token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
       detail="Invalid Refresh Token was provided"
    )

    if not refresh_token:
        raise invalid_token_exception

    result = await db.execute(
        select(RefreshToken)
        .filter(RefreshToken.token == refresh_token)
    )
    refresh_token_obj = result.scalar_one_or_none()
    if not refresh_token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token wasn't provided"
        )
    try:
        payload = jwt.decode(token=refresh_token_obj.token, key=settings.SECRET_KEY, algorithms=settings.ALGORITHM)
        token_exp = payload.get("exp", "")
        token_type = payload.get("type", "")
        token_sub = payload.get("sub", "")

        if not token_exp or not token_type or not token_sub:
            raise invalid_token_exception

        if int(token_exp) < int(datetime.now(timezone.utc).timestamp()) or token_type != "refresh":
            raise invalid_token_exception

    except JWTError:
        raise invalid_token_exception

    user = await get_user_by_email(email=token_sub, db=db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User from refresh token not exist")
    return user


async def login(
        db: AsyncSession,
        form_data: OAuth2PasswordRequestForm
):
    email = form_data.username
    password = form_data.password
    user = await get_user_by_email(email, db)
    if not user:
        return {"detail_404": "User by provided id not exists"}

    password_check = verify_password(password, user.hashed_password)
    if not password_check or not user:
        return {"detail_401": "Invalid email or password were provided"}

    data = {
        "type": "access",
        "sub": user.email,
        "role": user.user_group.name
    }
    access_token = create_token(
        data=data,
        expiration=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
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

    return {
        "refresh_token": refresh_token,
        "access_token": access_token,
        "refresh_expires_at": refresh_token_obj.expires_at
    }


async def token_refresh(
        user: User
) -> str:
    data = {
        "type": "access",
        "sub": user.email,
        "role": user.user_group.name
    }
    new_access_token = create_token(
        data=data,
        expiration=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return new_access_token


async def user_register(
        db: AsyncSession,
        data: CreateUserForm,
        background_tasks: BackgroundTasks
):
    user = await get_user_by_email(data.email, db)
    if user:
        return {"detail_409": "User with this email already exists."}

    result_group = await db.execute(
        select(UserGroup)
        .filter(UserGroup.id == data.group_id)
    )
    user_group = result_group.scalar_one_or_none()
    if not user_group:
        return {"detail_400": "Group by provided id does not exist"}

    try:
        hashed_password = get_hashed_password(data.password)
        user_create = User(
            email=str(data.email),
            hashed_password=hashed_password,
            group_id=data.group_id
        )
        db.add(user_create)
        await db.commit()
        await db.refresh(user_create)

        user_profile = UserProfile(
            user_id=user_create.id
        )
        activation_token = generate_secret_code()
        activation_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)

        activation_token_obj = ActivationToken(
            user_id=user_create.id,
            token=activation_token,
            expires_at=activation_code_expires_at
        )
        db.add(activation_token_obj)
        db.add(user_profile)
        await db.commit()
        await db.refresh(activation_token_obj)

        activation_link = f"{settings.WEBSITE_URL}/activate/{activation_token_obj.token}"

        async with aiofiles.open(
                "app/services/email_service/email_templates/register.html",
                "r"
        ) as f:
            register_html = await f.read()

        html = register_html.replace(
            "{{ user_email }}", user_create.email
        ).replace("{{ activation_link }}", activation_link)

    except Exception as e:
        await db.rollback()
        raise e

    else:
        user_name = user_profile.get_full_name()

        background_tasks.add_task(
            send_email,
            user_email=user_create.email,
            subject="Account Activation",
            html=html,
            user_name=user_name or "User"
        )
        return {"user_create": user_create}


async def activate_account(
        db: AsyncSession,
        token: str
):
    result_act_token = await db.execute(
        select(ActivationToken)
        .filter(ActivationToken.token == token)
        .options(selectinload(ActivationToken.user))
    )
    activation_token_obj = result_act_token.scalar_one_or_none()

    if not activation_token_obj:
        return {"detail_404": "Invalid activation token"}

    if activation_token_obj.expires_at.timestamp() < datetime.now(timezone.utc).timestamp():
        return RedirectResponse(f"{settings.WEBSITE_URL}/send_new_activation_token/{activation_token_obj.token}")

    try:
        user = activation_token_obj.user
        user.is_active = True
        await db.delete(activation_token_obj)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e

    return {"detail_200": {"detail": "You account was successfully activated!"}}


async def send_new_activation_token(
        db: AsyncSession,
        expired_token: str,
        data: SendNewActivationTokenSchema,
        background_tasks: BackgroundTasks
):
    result_act_token = await db.execute(
        select(ActivationToken)
        .filter(ActivationToken.token == expired_token)
        .options(joinedload(ActivationToken.user).options(
            joinedload(User.user_profile)
        ))
    )
    expired_activation_token_obj = result_act_token.scalar_one_or_none()

    if not expired_activation_token_obj:
        return {"detail_404": "Invalid activation token, was not found"}

    try:
        async with aiofiles.open(
                "app/services/email_service/email_templates/register.html",
                "r"
        ) as f:
            html_text = await f.read()

        new_activate_token = generate_secret_code()
        if data.email != expired_activation_token_obj.user.email:
            return {
                "detail_401": "Please enter your correct email. (Email which was just written isn't equal to your account email)"
            }

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

    except Exception as e:
        await db.rollback()
        raise e

    else:
        html = html_text.replace("{{ user_email }}", activation_token_new_obj.user.email).replace("{{ activation_link }}", activation_link)
        user_name = expired_activation_token_obj.user.user_profile.get_full_name()

        background_tasks.add_task(
            send_email,
            user_email=activation_token_new_obj.user.email,
            subject="New Activation Token",
            html=html,
            user_name=user_name or "User"
        )

        return {"detail_200": {"detail": "Just was sent new activation code"}}


async def logout(
        db: AsyncSession,
        user: User,
):
    result_refresh_token_to_delete = await db.execute(
        select(RefreshToken)
        .filter(RefreshToken.token == user.refresh_token.token)
    )
    refresh_token_to_delete = result_refresh_token_to_delete.scalar_one_or_none()

    if not refresh_token_to_delete:
        return {"detail_400": "Something went wrong during getting refresh token"}

    try:
        await db.delete(refresh_token_to_delete)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e

    return {"detail_200": {"detail": "Successfully logged out"}}


async def change_password_response(
        db: AsyncSession,
        data: ChangePasswordRequestSchema,
        background_tasks: BackgroundTasks
):
    user = await get_user_by_email(email=data.email, db=db)

    if not user:
        return {"detail_200": "ok"}

    try:
        async with aiofiles.open("app/services/email_service/email_templates/change_password.html", "r") as f:
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

    except Exception as e:
        await db.rollback()
        raise e

    else:
        html = html_template.replace("{{ user_email }}", user.email).replace("{{ change_password_link }}", change_password_link)
        user_name = user.user_profile.get_full_name()

        background_tasks.add_task(
            send_email,
            user_email=user.email,
            subject="Reset Password Code",
            html=html,
            user_name=user_name or "User"
        )
        return {"detail_200": "ok"}


async def change_password(
        db: AsyncSession,
        change_password_token: str,
        new_password_data: NewPasswordDataSchema
):
    result_reset_code = await db.execute(
        select(PasswordResetToken)
        .filter(PasswordResetToken.token == change_password_token)
        .options(joinedload(PasswordResetToken.user))
    )
    reset_code_obj = result_reset_code.scalar_one_or_none()

    if not reset_code_obj:
        return {"detail_404": "Reset code was not found."}

    if reset_code_obj.expires_at < datetime.now(timezone.utc):
        return {"detail_401": "Reset code is already expired"}

    user = reset_code_obj.user

    try:
        hashed_password = get_hashed_password(new_password_data.passoword1)

        user.hashed_password = hashed_password
        await db.delete(reset_code_obj)
        await db.commit()
        return {"detail_200": {"detail": "Successfully changed password"}}
    except Exception as e:
        await db.rollback()
        raise e

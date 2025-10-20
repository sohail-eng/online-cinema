from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, BackgroundTasks
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordRequestForm
from starlette import status
from starlette.responses import RedirectResponse, JSONResponse

import app
from app import crud
from app.crud.auth import login, validate_refresh_token, token_refresh, user_register, activate_account, \
    send_new_activation_token, logout, change_password_response, change_password
from app.models.user import User
from app.schemas.auth import LoginTokens, AccessToken, CreateUserForm, SendNewActivationTokenSchema, \
    ChangePasswordRequestSchema, NewPasswordDataSchema
from app.schemas.user import UserCreated
from app.utils.dependencies import DpGetDB
from app.utils.exceptions import SomethingWentWrongError

router = APIRouter()

@router.post("/login/", response_model=LoginTokens)
async def login_endpoint(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: DpGetDB,
        response: Response
):
    result_login = await app.crud.auth.login(
        db=db,
        form_data=form_data,
    )
    if not isinstance(result_login, dict):
        raise SomethingWentWrongError

    if result_login.get("detail_401", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(result_login.get("detail_401")))

    if result_login.get("detail_404", None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(result_login.get("detail_404")))

    response.set_cookie(
        key="refresh_token",
        value=result_login.get("refresh_token", ""),
        httponly=True,
        samesite="lax",
        secure=True,  # HTTPS <------------------------------
        expires=result_login.get("refresh_expires_at", "")
    )

    return LoginTokens(
        access_token=result_login.get("access_token", ""),
    )


@router.post("/token/refresh/")
async def refresh_token_endpoint(
        user: Annotated[User, Depends(validate_refresh_token)]
) -> AccessToken:
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Something went wrong. Try again.")

    new_access_token = await token_refresh(user=user)

    return AccessToken(access_token=new_access_token)


@router.post("/register/", response_model=UserCreated)
async def register_user_endpoint(
        db: DpGetDB,
        data: CreateUserForm,
        background_tasks: BackgroundTasks
):
    result_user_register = await user_register(
        db=db,
        data=data,
        background_tasks=background_tasks
    )
    if not isinstance(result_user_register, dict):
        raise SomethingWentWrongError

    if result_user_register.get("detail_409", ""):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(result_user_register.get("detail_409")))

    if result_user_register.get("detail_400", ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(result_user_register.get("detail_409")))

    if not isinstance(result_user_register.get("user_create"), User):
        raise SomethingWentWrongError

    return result_user_register.get("user_create")


@router.get("/activate/{token}/")
async def activate_account_endpoint(
        db: DpGetDB,
        token: str
):
    result_activate_account = await activate_account(
        db=db,
        token=token
    )
    if not isinstance(result_activate_account, dict):
        raise SomethingWentWrongError

    if result_activate_account.get("detail_404", None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(result_activate_account.get("detail_404")))

    if result_activate_account.get("token_expired_send_new_url", None):
        return RedirectResponse(url=str(result_activate_account.get("token_expired_send_new_url")))

    if result_activate_account.get("detail_200", None):
        return JSONResponse(content=result_activate_account.get("detail_200"), status_code=status.HTTP_200_OK)

    raise SomethingWentWrongError


@router.post("/send_new_activation_token/{expired_token}/")
async def send_new_activation_token_endpoint(
        db: DpGetDB,
        expired_token: str,
        data: SendNewActivationTokenSchema,
        background_tasks: BackgroundTasks
):
    result_send_activation_token = await send_new_activation_token(
        db=db,
        expired_token=expired_token,
        data=data,
        background_tasks=background_tasks
    )

    if not isinstance(result_send_activation_token, dict):
        raise SomethingWentWrongError

    if result_send_activation_token.get("detail_404", None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result_send_activation_token.get("detail_404"))

    if result_send_activation_token.get("detail_401", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_send_activation_token.get("detail_401")
        )
    if result_send_activation_token.get("detail_200"):
        return JSONResponse(content=result_send_activation_token.get("detail_200"), status_code=status.HTTP_200_OK)

    raise SomethingWentWrongError


@router.get("/logout/")
async def logout_endpoint(
        db: DpGetDB,
        user: Annotated[User, Depends(validate_refresh_token)]
):
    result_logout = await logout(
        db=db,
        user=user
    )

    if not isinstance(result_logout, dict):
        raise SomethingWentWrongError

    if result_logout.get("detail_400", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result_logout.get("detail_400")
        )

    response = JSONResponse(
        content=result_logout.get("detail_200"),
        status_code=status.HTTP_200_OK
    )

    response.delete_cookie("refresh_token")
    return response


@router.post("/change_password/")
async def change_password_response_endpoint(
        db: DpGetDB,
        data: ChangePasswordRequestSchema,
        background_tasks: BackgroundTasks
):
    result_change_password_response = await change_password_response(
        db=db,
        data=data,
        background_tasks=background_tasks
    )

    if not isinstance(result_change_password_response, dict):
        raise SomethingWentWrongError

    if result_change_password_response.get("detail_200"):
        return JSONResponse(
            content={"detail": "We have just sent a Reset Code if account by provided email exists"},
            status_code=status.HTTP_200_OK
        )


@router.post("/change_password/{change_password_token}/")
async def change_password_endpoint(
        db: DpGetDB,
        change_password_token: str,
        new_password_data: NewPasswordDataSchema
):
    result_change_password = await change_password(
        db=db,
        change_password_token=change_password_token,
        new_password_data=new_password_data
    )

    if not isinstance(result_change_password, dict):
        raise SomethingWentWrongError

    if result_change_password.get("detail_404", None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result_change_password.get("detail_404")
        )

    if result_change_password.get("detail_401", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_change_password.get("detail_401")
        )

    if result_change_password.get("detail_200", None):
        return JSONResponse(
            content=result_change_password.get("detail_200"),
            status_code=status.HTTP_200_OK
        )

    raise SomethingWentWrongError

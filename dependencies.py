from typing import Annotated
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import models
from database import get_db
from settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/")

DpGetDB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DpGetDB) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        token_expire = payload.get("exp")
        role = payload.get("role")

        if email is None or token_expire is None or role is None:
            raise credentials_exception

        if datetime.fromtimestamp(token_expire) < datetime.now():
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

    except JWTError:
        raise credentials_exception

    from crud import get_user_by_email

    current_user = await get_user_by_email(db=db, email=email)

    if not current_user:
        raise credentials_exception
    return current_user


GetCurrentUser = Annotated[models.User, Depends(get_current_user)]



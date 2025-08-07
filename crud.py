from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import models
from database import get_db


DpGetDB = Annotated[AsyncSession, Depends(get_db)]

async def get_user_by_email(email, db = DpGetDB) -> models.User | None:
    result = await db.execute(select(models.User).filter(models.User.email == email))
    user = result.scalar_one_or_none()
    return user

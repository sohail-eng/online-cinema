from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import models
from database import get_db

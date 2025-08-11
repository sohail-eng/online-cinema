from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette import status
from starlette.responses import JSONResponse

from database import engine
from exceptions import UserDontHavePermissionError, MovieNotFoundError, SomethingWentWrongError, CommentNotFoundError
from models import Base
from routers import users, movies, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield

from routers import users, movies


@app.exception_handler(UserDontHavePermissionError)
async def handler_user_dont_have_permission_error(request, exception):
    return JSONResponse(
        content="Users have not permissions to delete movies.",
        status_code=status.HTTP_403_FORBIDDEN
    )

app.include_router(users.router)
app.include_router(movies.router)

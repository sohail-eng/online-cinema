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

app = FastAPI(lifespan=lifespan)


@app.exception_handler(UserDontHavePermissionError)
async def handler_user_dont_have_permission_error(request, exception):
    return JSONResponse(
        content="Users have not permissions to delete movies.",
        status_code=status.HTTP_403_FORBIDDEN
    )

@app.exception_handler(MovieNotFoundError)
async def handler_movie_not_found_error(request, exception):
    return JSONResponse(
        content="Movie was not found",
        status_code=status.HTTP_404_NOT_FOUND
    )

@app.exception_handler(SomethingWentWrongError)
async def handler_something_went_wrong(request, exception):
    return JSONResponse(
        content="Something went wrong",
        status_code=status.HTTP_400_BAD_REQUEST
    )

@app.exception_handler(CommentNotFoundError)
async def handler_comment_not_found_error(request, exception):
    return JSONResponse(
        content="Comment was not found",
        status_code=status.HTTP_404_NOT_FOUND
    )

app.include_router(users.router)
app.include_router(movies.router)


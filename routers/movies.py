from typing import List

from fastapi import APIRouter
from starlette import status
from starlette.responses import JSONResponse

import crud
import dependencies
import models
import schemas
from crud import get_movie_by_id
from exceptions import SomethingWentWrongError
from schemas import MovieReadDetail

router = APIRouter()

@router.get("/movies")
async def movies_list():
    return {"message": "All Movies"}

@router.get("/movies/", response_model=List[schemas.MovieRead])
async def movies_list_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        favorite_list: bool = False,
        skip: int = 0,
        limit: int = 20,
        filter_imdb: int = None,
        filter_release_year: int = None,
        sort_release_year: int = None,
        sort_price: int = None,
        sort_popularity: int = None,
        sort_format: str = "desc",
        search_name: str = None,
        search_director: str = None,
        search_actor: str = None,
        search_description: str = None
):
    filtered_movies = await crud.read_movies(
        db=db,
        user_profile=user.user_profile,
        skip=skip,
        limit=limit,
        favorite_list=favorite_list,
        filter_imdb=filter_imdb,
        filter_release_year=filter_release_year,
        sort_release_year=sort_release_year,
        sort_price=sort_price,
        sort_popularity=sort_popularity,
        sort_format=sort_format,
        search_name=search_name,
        search_director=search_director,
        search_actor=search_actor,
        search_description=search_description
    )


    if not filtered_movies:
        return JSONResponse({"detail": "Movies not found"}, status_code=404)

    return filtered_movies


@router.get("/movies/{movie_id}/", response_model=schemas.MovieReadDetail)
async def movie_detail_endpoint(
        movie_id: int,
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser
) -> MovieReadDetail:

    movie_dict = await get_movie_by_id(movie_id=movie_id, db=db, user_profile=user.user_profile)
    movie_detail = schemas.MovieReadDetail.model_validate(movie_dict.get("movie"))
    movie_detail = movie_detail.model_copy(update={
        "average_rate_in_stars": movie_dict.get("average_rate_in_stars"),
        "in_favorite_by_current_user": movie_dict.get("in_favorite_by_current_user"),
        "current_user_star_rating": movie_dict.get("current_user_star_rating"),
        "current_user_like_or_dislike": movie_dict.get("current_user_like_or_dislike"),
        "liked_comments_current_movie_ids": movie_dict.get("liked_comments_current_movie_ids"),
        "count_of_likes_current_movie": movie_dict.get("count_of_likes_current_movie"),
        "count_of_dislikes_current_movie": movie_dict.get("count_of_dislikes"),
        "current_user_comment_ids": movie_dict.get("current_user_comment_ids"),
        "current_user_replies_ids": movie_dict.get("current_user_replies_ids")
    })
    return movie_detail


@router.post("/movies/{movie_id}/delete/")
async def movie_delete_endpoint(
        movie_id: int,
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser
) -> JSONResponse:
    deleted_movie = await crud.delete_movie(movie_id=movie_id, db=db, user_profile=user.user_profile)

    if not isinstance(deleted_movie, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{deleted_movie.get('detail')}", status_code=status.HTTP_200_OK)


@router.post("/movies/{movie_id}/update/", response_model=schemas.MovieRead)
async def movie_update_endpoint(
        movie_id: int,
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        data: schemas.MovieUpdateScheme
) -> models.Movie:
    updated_movie = await crud.update_movie(movie_id=movie_id, db=db, user_profile=user.user_profile, data=data)

    if not isinstance(updated_movie, models.Movie):
        raise SomethingWentWrongError

    return updated_movie


@router.post("/movies/create/", response_model=schemas.MovieReadDetail)
async def movie_create_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        data: schemas.MovieCreateSchema
):
    created_movie = await crud.movie_create(db=db, user_profile=user.user_profile, data=data)

    if not isinstance(created_movie, models.Movie):
        raise SomethingWentWrongError

    return created_movie


@router.post("/movies/{movie_id}/create_comment/", response_model=schemas.CommentReadAfterCreationSchema)
async def movie_create_comment_endpoint(
        movie_id: int,
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        data: schemas.CommentCreateSchema
):
    created_comment = await crud.create_comment(
        movie_id=movie_id,
        db=db,
        user_profile=user.user_profile,
        data=data
    )

    if not isinstance(created_comment, models.MovieComment):
        raise SomethingWentWrongError

    return created_comment



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

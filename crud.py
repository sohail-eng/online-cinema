from typing import Annotated, Any, Coroutine, Sequence

from fastapi import Depends, HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import models
import schemas



async def read_movies(
        db: AsyncSession,
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
    query = select(models.Movie)

    if search_name:
        query = query.filter(models.Movie.name.ilike(f"%{search_name}%"))

    if search_director:
        query = query.filter(models.Movie.directors.any(models.Director.name.ilike(f"%{search_director}%")))

    if search_actor:
        query = query.filter(models.Movie.stars.any(models.Star.name.ilike(f"%{search_actor}%")))

    if search_description:
        query = query.filter(models.Movie.description.ilike(f"%{search_description}%"))

    if filter_imdb:
        query = query.filter(models.Movie.imdb == filter_imdb)

    if filter_release_year:
        query = query.filter(models.Movie.year == filter_release_year)

    if sort_release_year:
        if sort_format == "desc":
            query = query.order_by(models.Movie.year.desc())
        elif sort_format == "asc":
            query = query.order_by(models.Movie.year.asc())

    if sort_price:
        if sort_format == "desc":
            query = query.order_by(models.Movie.price.desc())
        elif sort_format == "asc":
            query = query.order_by(models.Movie.price.asc())

    if sort_popularity:
        query = query.order_by(models.Movie.votes.desc())


    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def create_comment(movie_id: int, db: AsyncSession, data: schemas.CommentCreateSchema, user: models.UserProfile) -> models.MovieComment | None:
    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        return None

    comment = models.MovieComment(
        user_profile_id=user.id,
        movie_id=movie.id,
        text=data.text
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return comment


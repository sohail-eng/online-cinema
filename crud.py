from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
import schemas
from exceptions import CommentNotFoundError, MovieNotFoundError, UserDontHavePermissionError


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
) -> Sequence[models.Movie] | None:

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


async def create_comment(
        movie_id: int, db:
        AsyncSession, data: schemas.CommentCreateSchema,
        user: models.UserProfile
) -> MovieNotFoundError | models.MovieComment | Exception:

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        comment = models.MovieComment(
            user_profile_id=user.id,
            movie_id=movie.id,
            text=data.text
        )
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return comment
    except Exception as e:
        await db.rollback()
        raise e


async def delete_comment(
        comment_id: int,
        db: AsyncSession,
        user_profile: models.UserProfile
) -> CommentNotFoundError | None | Exception:

    if user_profile.user.user_group.name == models.UserGroupEnum.user:
        raise UserDontHavePermissionError("Permissions for deleting have Admins and Moderators, not regular Users")

    result_comment = await db.execute(select(models.MovieComment).filter(models.MovieComment.id == comment_id))
    comment = result_comment.scalar_one_or_none()

    if not comment:
        raise CommentNotFoundError("Comment was not found")

    try:
        await db.delete(comment)
        await db.commit()
        return None
    except Exception as e:
        await db.rollback()
        raise e


async def reply_comment(
        comment_id: int,
        db: AsyncSession,
        user_profile: models.UserProfile,
        data: schemas.CommentCreateSchema
) -> Exception | CommentNotFoundError | models.MovieCommentReply:

    result_comment = await db.execute(select(models.MovieComment).filter(
        models.MovieComment.id == comment_id)
    )
    comment = result_comment.scalar_one_or_none()

    if not comment:
        raise CommentNotFoundError("Comment was not found")
    try:
        comment_reply = models.MovieCommentReply(
            comment_id=comment.id,
            user_profile_id=user_profile.id,
            text=data.text
        )
        db.add(comment_reply)
        await db.commit()
        await db.refresh(comment_reply)
        return comment_reply
    except Exception as e:
        await db.rollback()
        raise e


async def like_comment_or_delete_if_exists(
        comment_id: int,
        db: AsyncSession,
        user_profile: models.UserProfile
) -> Exception | CommentNotFoundError | dict[str, str]:

    result_comment = await db.execute(select(models.MovieComment).filter(
        models.MovieComment.id == comment_id)
    )
    comment = result_comment.scalar_one_or_none()

    if not comment:
        raise CommentNotFoundError("Comment was not found")
    try:
        exist_result = await db.execute(select(models.MovieCommentLike).filter(
            models.MovieCommentLike.user_profile_id == user_profile.id,
            models.MovieCommentLike.comment_id == comment.id)
        )
        existing_comment_like = exist_result.scalar_one_or_none()

        if not existing_comment_like:
            comment_like = models.MovieCommentLike(
                user_profile_id=user_profile.id,
                comment_id=comment.id
            )
            comment.votes += 1
            db.add(comment_like)
            message = "Comment was liked"
        else:
            await db.delete(existing_comment_like)
            comment.votes -= 1
            message = "Comment was unliked"

        await db.commit()
        return {"detail": message}
    except Exception as e:
        await db.rollback()
        raise e


async def add_movie_to_favorite_or_delete_if_exists(
        movie_id: int,
        user_profile: models.UserProfile,
        db: AsyncSession
) -> MovieNotFoundError | Exception | dict[str, str]:

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        exist_result = await db.execute(select(models.MovieFavorite).filter(
            models.MovieFavorite.user_profile_id == user_profile.id,
            models.MovieFavorite.movie_id == movie.id)
        )
        existing_favorite = exist_result.scalar_one_or_none()

        if not existing_favorite:
            user_favorite = models.MovieFavorite(
                movie_id=movie_id,
                user_profile_id=user_profile.id
            )
            db.add(user_favorite)
            message = "Movie was added to favorite"
        else:
            await db.delete(existing_favorite)
            message = "Movie was deleted from favorite"

        await db.commit()
        return {"detail": message}
    except Exception as e:
        await db.rollback()
        raise e


async def like_or_dislike_movie_and_delete_if_exists(
        movie_id: int,
        user_profile: models.UserProfile,
        db: AsyncSession,
        data: schemas.UserMovieRating
) -> MovieNotFoundError | dict[str, str] | Exception:

    result_movie = await db.execute(select(models.Movie).filter(
        models.Movie.id == movie_id)
    )
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    try:
        existing_result = await db.execute(select(models.MovieRating).filter(
            models.MovieRating.user_profile_id == user_profile.id,
            models.MovieRating.movie_id == movie.id)
        )
        existing_rating = existing_result.scalar_one_or_none()

        if not existing_rating:
            user_rating = models.MovieRating(
                user_profile_id=user_profile.id,
                movie_id=movie.id,
                rating=data.rating
            )
            movie.votes += 1
            db.add(user_rating)
            message = "Rating was Created"

        else:
            await db.delete(existing_rating)
            movie.votes -= 1
            message = "Rating was Deleted"

        await db.commit()
        return {"detail": message}
    except Exception as e:
        await db.rollback()
        raise e
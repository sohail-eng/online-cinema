from typing import Sequence

import aiofiles
from fastapi import BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.cart import CartItem
from app.models.movie import Movie, MovieFavorite, Director, MovieComment, MovieCommentReply, MovieStar, MovieRating, \
    MovieRatingEnum, MovieCommentLike, Star, Genre
from app.models.user import UserProfile, User, UserGroupEnum
from app.schemas.movie import CommentCreateSchema, MovieCommentReplyCreate, UserMovieRating, MovieRatingFromZeroToTen, \
    MovieCreateSchema, MovieUpdateScheme
from app.services.email_service.email_sender import send_email
from app.utils.exceptions import MovieNotFoundError, CommentNotFoundError, UserDontHavePermissionError, \
    SomethingWentWrongError


async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession,
        user_profile: UserProfile
) -> dict[str, Movie | bool] | MovieNotFoundError | Exception:
    result_movie = await db.execute(select(Movie).filter(Movie.id == movie_id).options(
        selectinload(Movie.stars),
        selectinload(Movie.genres),
        selectinload(Movie.directors),

        selectinload(Movie.movie_comments).options(
            selectinload(MovieComment.movie_comment_replies).options(
                selectinload(MovieCommentReply.user_profile).options(
                    selectinload(UserProfile.user).joinedload(User.user_group)
                ),
            ),
            selectinload(MovieComment.user_profile).options(
                selectinload(UserProfile.user).joinedload(User.user_group)
            ),
        ),
        selectinload(Movie.movie_rate_in_stars),
        selectinload(Movie.movie_favorites),
        selectinload(Movie.movie_ratings),
        joinedload(Movie.certification)
    ))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        result_movie_user_star = await db.execute(select(MovieStar.rate).filter(
            MovieStar.user_profile_id == user_profile.id,
            MovieStar.movie_id == movie.id)
        )
        result_current_user_like_or_dislike = await db.execute(select(MovieRating.rating).filter(
            MovieRating.user_profile_id == user_profile.id,
            MovieRating.movie_id == movie.id)
        )
        result_count_of_likes = await db.execute(select(func.count().filter(
            MovieRating.rating == MovieRatingEnum.like))
        )

        result_count_of_dislikes = await db.execute(select(func.count()).filter(
            MovieRating.rating == MovieRatingEnum.dislike)
        )

        result_current_user_replies_ids = await db.execute(select(MovieCommentReply.id).filter(
            MovieCommentReply.user_profile_id == user_profile.id,
            MovieCommentReply.movie_comment.has(
                MovieComment.movie_id == movie.id
            )
        ))

        result_current_user_comment_ids = await db.execute(select(MovieComment.id).filter(
            MovieComment.user_profile_id == user_profile.id,
            MovieComment.movie_id == movie.id
        ))

        result_liked_comments_current_movie = await db.execute(select(MovieCommentLike.comment_id).filter(
            MovieCommentLike.user_profile_id == user_profile.id,
            MovieCommentLike.movie_comment.has(MovieComment.movie_id == movie.id)
        )
        )

        result_all_rates = await db.execute(select(MovieStar.rate).filter(MovieStar.movie_id == movie.id))
        all_rates = result_all_rates.scalars().all()
        if not all_rates:
            average_rate_in_stars = 0.0
        else:
            sum_of_all_rates = sum(all_rates)
            length = len(all_rates)

            average_rate_in_stars = sum_of_all_rates / length

        current_user_star_rating = result_movie_user_star.scalar_one_or_none()
        current_user_like_or_dislike = result_current_user_like_or_dislike.scalar_one_or_none()
        in_favorite_by_current_user = True if user_profile.user.id in movie.movie_favorites else False
        count_of_likes = result_count_of_likes.scalar_one_or_none()
        count_of_dislikes = result_count_of_dislikes.scalar_one_or_none()

        count_of_ratings = len(movie.movie_ratings)
        count_of_comments = len(movie.movie_comments)
        count_of_favorites = len(movie.movie_favorites)

        current_user_comment_ids = result_current_user_comment_ids.scalars().all()
        current_user_replies_ids = result_current_user_replies_ids.scalars().all()
        liked_comments_current_movie_ids = result_liked_comments_current_movie.scalars().all()

        return {
            "movie": movie,
            "in_favorite_by_current_user": in_favorite_by_current_user,
            "current_user_star_rating": current_user_star_rating,
            "current_user_like_or_dislike": current_user_like_or_dislike,
            "liked_comments_current_movie_ids": liked_comments_current_movie_ids,
            "count_of_likes_current_movie": count_of_likes,
            "count_of_dislikes_current_movie": count_of_dislikes,
            "current_user_comment_ids": current_user_comment_ids,
            "current_user_replies_ids": current_user_replies_ids,
            "average_rate_in_stars": average_rate_in_stars,
            "count_of_ratings": count_of_ratings,
            "count_of_comments": count_of_comments,
            "count_of_favorites": count_of_favorites
        }
    except Exception as e:
        print("An error occurred in get_movie_by_id")
        raise e


async def read_movies(
        db: AsyncSession,
        user_profile: UserProfile,
        skip: int = 0,
        limit: int = 20,
        favorite_list: bool = False,
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
) -> Sequence[Movie] | None:
    query = select(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.stars),
        selectinload(Movie.movie_comments),
        selectinload(Movie.directors),
        selectinload(Movie.movie_ratings),
        selectinload(Movie.movie_favorites),
        selectinload(Movie.movie_rate_in_stars),
        joinedload(Movie.certification)
    )

    if favorite_list:
        subquery = select(MovieFavorite.movie_id).filter(MovieFavorite.user_profile_id == user_profile.id)
        query = query.filter(Movie.id.in_(subquery.scalar_subquery()))

    if search_name:
        query = query.filter(Movie.name.ilike(f"%{search_name}%"))

    if search_director:
        query = query.filter(Movie.directors.any(Director.name.ilike(f"%{search_director}%")))

    if search_actor:
        query = query.filter(Movie.stars.any(Star.name.ilike(f"%{search_actor}%")))

    if search_description:
        query = query.filter(Movie.description.ilike(f"%{search_description}%"))

    if filter_imdb:
        query = query.filter(Movie.imdb == filter_imdb)

    if filter_release_year:
        query = query.filter(Movie.year == filter_release_year)

    if sort_release_year:
        if sort_format == "desc":
            query = query.order_by(Movie.year.desc())
        elif sort_format == "asc":
            query = query.order_by(Movie.year.asc())

    if sort_price:
        if sort_format == "desc":
            query = query.order_by(Movie.price.desc())
        elif sort_format == "asc":
            query = query.order_by(Movie.price.asc())

    if sort_popularity:
        query = query.order_by(Movie.votes.desc())

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def create_comment(
        movie_id: int, db:
        AsyncSession, data: CommentCreateSchema,
        user_profile: UserProfile
) -> MovieNotFoundError | MovieComment | Exception:
    result_movie = await db.execute(select(Movie).filter(Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        comment = MovieComment(
            user_profile_id=user_profile.id,
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
        user_profile: UserProfile
) -> CommentNotFoundError | dict[str, str] | Exception:
    if user_profile.user.user_group.name == UserGroupEnum.user:
        raise UserDontHavePermissionError(
            "Permissions for deleting have Admins and Moderators, not regular Users"
        )

    result_comment = await db.execute(
        select(MovieComment)
        .filter(MovieComment.id == comment_id)
    )
    comment = result_comment.scalar_one_or_none()

    if not comment:
        raise CommentNotFoundError("Comment was not found")

    try:
        await db.delete(comment)
        await db.commit()
        return {"detail": "Comment was successfully deleted"}
    except Exception as e:
        await db.rollback()
        raise e


async def reply_comment(
        comment_id: int,
        db: AsyncSession,
        user_profile: UserProfile,
        data: MovieCommentReplyCreate,
        background_task: BackgroundTasks
) -> Exception | CommentNotFoundError | MovieCommentReply:
    result_comment = await db.execute(
        select(MovieComment)
        .filter(MovieComment.id == comment_id)
        .options(
        joinedload(MovieComment.user_profile),
        joinedload(UserProfile.user)
        )
    )
    comment = result_comment.scalar_one_or_none()

    if not comment:
        raise CommentNotFoundError("Comment was not found")

    try:
        result_reply_comment_creator = await db.execute(select(UserProfile).filter(
            UserProfile.id == comment.user_profile_id
        ).options(joinedload(UserProfile.user)))

        reply_comment_creator = result_reply_comment_creator.scalar_one_or_none()

        if not reply_comment_creator:
            raise SomethingWentWrongError("Creator does not exists.")

        async with aiofiles.open("app/services/email_service/email_templates/reply_comment.html", "r") as f:
            reply_comment_html = await f.read()

        result_comment_movie_name = await db.execute(
            select(Movie.name).filter(Movie.id == comment.movie_id))
        comment_movie_name = result_comment_movie_name.scalar_one_or_none()

        recipient_name = (reply_comment_creator.first_name + " " + reply_comment_creator.last_name) if (
                reply_comment_creator.first_name and reply_comment_creator.last_name
        ) else reply_comment_creator.user.email

        reply_author = (comment.user_profile.first_name + " " + comment.user_profile.last_name) if (
                comment.user_profile.first_name and comment.user_profile.last_name
        ) else comment.user_profile.user.email

        reply_comment_html = reply_comment_html.replace(
            "{{recipient_name}}", recipient_name
        ).replace(
            "{{movie_title}}", comment_movie_name or "Without Name"
        ).replace(
            "{{reply_author}}", reply_author
        ).replace(
            "{{comment_text}}", comment.text
        ).replace(
            "{{reply_text}}", data.text
        )

        comment_reply = MovieCommentReply(
            comment_id=comment.id,
            user_profile_id=user_profile.id,
            text=data.text
        )
        db.add(comment_reply)
        await db.commit()
        await db.refresh(comment_reply)

    except Exception as e:
        await db.rollback()
        raise e

    else:
        if reply_comment_creator.user.email:
            user_profile_full_name = user_profile.get_full_name()

            background_task.add_task(
                send_email,
                user_email=reply_comment_creator.user.email,
                subject="You have just got new reply for your comment.",
                html=reply_comment_html,
                user_name=user_profile_full_name or "User"
            )
        return comment_reply


async def like_comment_or_delete_if_exists(
        comment_id: int,
        db: AsyncSession,
        user_profile: UserProfile
) -> Exception | CommentNotFoundError | dict[str, str]:
    result_comment = await db.execute(
        select(MovieComment)
        .filter(MovieComment.id == comment_id)
    )
    comment = result_comment.scalar_one_or_none()

    if not comment:
        raise CommentNotFoundError("Comment was not found")
    try:
        exist_result = await db.execute(select(MovieCommentLike).filter(
            MovieCommentLike.user_profile_id == user_profile.id,
            MovieCommentLike.comment_id == comment.id)
        )
        existing_comment_like = exist_result.scalar_one_or_none()

        if not existing_comment_like:
            comment_like = MovieCommentLike(
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
        user_profile: UserProfile,
        db: AsyncSession
) -> MovieNotFoundError | Exception | dict[str, str]:
    result_movie = await db.execute(
        select(Movie)
        .filter(Movie.id == movie_id)
    )
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        exist_result = await db.execute(
            select(MovieFavorite)
            .filter(
            MovieFavorite.user_profile_id == user_profile.id,
            MovieFavorite.movie_id == movie.id)
        )
        existing_favorite = exist_result.scalar_one_or_none()

        if not existing_favorite:
            user_favorite = MovieFavorite(
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
        user_profile: UserProfile,
        db: AsyncSession,
        data: UserMovieRating
) -> MovieNotFoundError | dict[str, str] | Exception:
    result_movie = await db.execute(select(Movie).filter(
        Movie.id == movie_id)
    )
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    try:
        existing_result = await db.execute(
            select(MovieRating)
            .filter(
            MovieRating.user_profile_id == user_profile.id,
            MovieRating.movie_id == movie.id)
        )
        existing_rating = existing_result.scalar_one_or_none()

        if not existing_rating:
            user_rating = MovieRating(
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


async def like_comment_reply_or_delete_if_exists(
        comment_reply_id: int,
        db: AsyncSession,
        user_profile: UserProfile
) -> Exception | CommentNotFoundError | dict[str, str]:
    result_comment_reply = await db.execute(select(MovieCommentReply).filter(
        MovieCommentReply.id == comment_reply_id)
    )
    comment_reply = result_comment_reply.scalar_one_or_none()

    if not comment_reply:
        raise CommentNotFoundError("Reply comment was not found")
    try:
        exist_result = await db.execute(
            select(MovieCommentLike)
            .filter(
            MovieCommentLike.user_profile_id == user_profile.id,
            MovieCommentLike.comment_id == comment_reply.id
            )
        )
        existing_comment_like = exist_result.scalar_one_or_none()

        if not existing_comment_like:
            comment_like = MovieCommentLike(
                user_profile_id=user_profile.id,
                comment_id=comment_reply.id
            )
            comment_reply.votes += 1
            db.add(comment_like)
            message = "Comment was liked"
        else:
            await db.delete(existing_comment_like)
            comment_reply.votes -= 1
            message = "Comment was unliked"

        await db.commit()
        return {"detail": message}
    except Exception as e:
        await db.rollback()
        raise e


async def rate_movie_from_0_to_10_or_delete_rate_if_exists(
        db: AsyncSession,
        movie_id: int,
        data: MovieRatingFromZeroToTen,
        user_profile: UserProfile
) -> dict[str, str] | MovieNotFoundError | Exception:
    result_movie = await db.execute(select(Movie).filter(Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    try:
        result_exist = await db.execute(
            select(MovieStar)
            .filter(
                MovieStar.movie_id == movie.id,
            MovieStar.user_profile_id == user_profile.id
            )
        )
        existing_stars_rate = result_exist.scalar_one_or_none()
        if not existing_stars_rate:
            rate = MovieStar(
                user_profile_id=user_profile.id,
                movie_id=movie.id,
                rate=data.rate
            )
            db.add(rate)
            message = "Stars rate was created"
        else:
            await db.delete(existing_stars_rate)
            message = "Stars rate was deleted"

        await db.commit()
        return {"detail": message}

    except Exception as e:
        await db.rollback()
        raise e


async def movie_create(
        db: AsyncSession,
        user_profile: UserProfile,
        data: MovieCreateSchema
) -> Movie | UserDontHavePermissionError | Exception:
    if user_profile.user.user_group.name is UserGroupEnum.user:
        raise UserDontHavePermissionError("User have not permissions to create new movies")

    import uuid
    movie_uuid = uuid.uuid4()
    try:
        result_genres = await db.execute(select(Genre).filter(Genre.id.in_(data.genre_ids)))
        genres = result_genres.scalars().all()

        result_stars = await db.execute(select(Star).filter(Star.id.in_(data.star_ids)))
        stars = result_stars.scalars().all()

        result_directors = await db.execute(select(Director).filter(Director.id.in_(data.director_ids)))
        directors = result_directors.scalars().all()

        new_movie = Movie(
            uuid=movie_uuid,
            name=data.name,
            year=data.year,
            time=data.time,
            imdb=data.imdb,
            votes=data.votes,
            meta_score=data.meta_score,
            gross=data.gross,
            description=data.description,
            price=data.price,
            certification_id=data.certification_id,
            # m2m
            genres=genres,
            directors=directors,
            stars=stars
        )
        db.add(new_movie)
        await db.commit()
        await db.refresh(new_movie)

        return new_movie
    except Exception as e:
        await db.rollback()
        raise e


async def delete_movie(
        movie_id: int,
        db: AsyncSession,
        user_profile: UserProfile
) -> UserDontHavePermissionError | dict[str, str] | Exception:
    if user_profile.user.user_group.name is UserGroupEnum.user:
        raise UserDontHavePermissionError("User have not permissions to delete movies")

    result_movie = await db.execute(select(Movie).filter(Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    result_movie_in_users_cart = await db.execute(
        select(CartItem.id).filter(CartItem.movie_id == movie.id))
    movie_in_users_cart = result_movie_in_users_cart.scalars().all()

    if not movie_in_users_cart:
        try:
            await db.delete(movie)
            await db.commit()
            return {"detail": "Movie was successfully deleted."}
        except Exception as e:
            await db.rollback()
            raise e
    else:
        return {"detail": "You can not delete the movie because it is in user's cart"}


async def update_movie(
        movie_id: int,
        db: AsyncSession,
        user_profile: UserProfile,
        data: MovieUpdateScheme
):
    if user_profile.user.user_group.name in UserGroupEnum.user:
        raise UserDontHavePermissionError("User have no permissions for updating movies")

    result_movie = await db.execute(select(Movie).filter(Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            if field not in ["genre_ids", "director_ids", "star_ids"]:
                setattr(movie, field, value)

        if data.genre_ids:
            result_genres = await db.execute(select(Genre).filter(Genre.id.in_(data.genre_ids)))
            movie.genres = result_genres.scalars().all()

        if data.director_ids:
            result_directors = await db.execute(
                select(Director).filter(Director.id.in_(data.director_ids)))
            movie.directors = result_directors.scalars().all()

        if data.star_ids:
            result_stars = await db.execute(select(Star).filter(Star.id.in_(data.star_ids)))
            movie.stars = result_stars.scalars().all()

        await db.commit()
        await db.refresh(movie)
        return movie
    except Exception as e:
        await db.rollback()
        raise e
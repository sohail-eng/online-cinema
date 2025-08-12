from typing import Sequence, Any

import aiofiles
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.sql.functions import func

import models
import schemas
from email_service.email_sender import send_email
from exceptions import CommentNotFoundError, MovieNotFoundError, UserDontHavePermissionError, SomethingWentWrongError, \
    MovieAlreadyIsPurchasedOrInCartError, CartNotExistError
from models import CartItem, Cart


async def get_user_by_email(email, db: AsyncSession) -> models.User | None:
    result = await db.execute(select(models.User).filter(models.User.email == email).options(
        joinedload(models.User.user_group),
        joinedload(models.User.user_profile).options(
            joinedload(models.UserProfile.cart).options(selectinload(models.Cart.cart_items)
                                                        )
        ),
    ))
    user = result.scalar_one_or_none()
    return user


async def read_movies(
        db: AsyncSession,
        user_profile: models.UserProfile,
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
) -> Sequence[models.Movie] | None:

    query = select(models.Movie).options(
        selectinload(models.Movie.genres),
        selectinload(models.Movie.stars),
        selectinload(models.Movie.movie_comments),
        selectinload(models.Movie.directors),
        selectinload(models.Movie.movie_ratings),
        selectinload(models.Movie.movie_favorites),
        selectinload(models.Movie.movie_rate_in_stars),
        joinedload(models.Movie.certification)
    )

    if favorite_list:
        subquery = select(models.MovieFavorite.movie_id).filter(models.MovieFavorite.user_profile_id == user_profile.id)
        query = query.filter(models.Movie.id.in_(subquery.scalar_subquery()))

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
        user_profile: models.UserProfile
) -> MovieNotFoundError | models.MovieComment | Exception:

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        comment = models.MovieComment(
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
        user_profile: models.UserProfile
) -> CommentNotFoundError | dict[str, str] | Exception:

    if user_profile.user.user_group.name == models.UserGroupEnum.user:
        raise UserDontHavePermissionError("Permissions for deleting have Admins and Moderators, not regular Users")

    result_comment = await db.execute(select(models.MovieComment).filter(models.MovieComment.id == comment_id))
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
        user_profile: models.UserProfile,
        data: schemas.MovieCommentReplyCreate,
        background_task: BackgroundTasks
) -> Exception | CommentNotFoundError | models.MovieCommentReply:

    result_comment = await db.execute(select(models.MovieComment).filter(
        models.MovieComment.id == comment_id).options(
        joinedload(models.MovieComment.user_profile),
        joinedload(models.UserProfile.user)
    )
    )
    comment = result_comment.scalar_one_or_none()

    if not comment:
        raise CommentNotFoundError("Comment was not found")

    try:
        result_reply_comment_creator = await db.execute(select(models.UserProfile).filter(
            models.UserProfile.id == comment.user_profile_id
        ).options(joinedload(models.UserProfile.user)))

        reply_comment_creator = result_reply_comment_creator.scalar_one_or_none()

        if not reply_comment_creator:
            raise SomethingWentWrongError("Creator does not exists.")

        async with aiofiles.open("email_service/email_templates/reply_comment.html", "r") as f:
            reply_comment_html = await f.read()

        result_comment_movie_name = await db.execute(
            select(models.Movie.name).filter(models.Movie.id == comment.movie_id))
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

        if reply_comment_creator.user.email:
            background_task.add_task(
                send_email,
                user_email=reply_comment_creator.user.email,
                subject="You have just got new reply for your comment.",
                html=reply_comment_html
            )

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


async def like_comment_reply_or_delete_if_exists(
        comment_reply_id: int,
        db: AsyncSession,
        user_profile: models.UserProfile
) -> Exception | CommentNotFoundError | dict[str, str]:

    result_comment_reply = await db.execute(select(models.MovieCommentReply).filter(
        models.MovieCommentReply.id == comment_reply_id)
    )
    comment_reply = result_comment_reply.scalar_one_or_none()

    if not comment_reply:
        raise CommentNotFoundError("Reply comment was not found")
    try:
        exist_result = await db.execute(select(models.MovieCommentLike).filter(
            models.MovieCommentLike.user_profile_id == user_profile.id,
            models.MovieCommentLike.comment_id == comment_reply.id)
        )
        existing_comment_like = exist_result.scalar_one_or_none()

        if not existing_comment_like:
            comment_like = models.MovieCommentLike(
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


async def rate_movie_from_0_to_10_or_delete_rate_if_exists(
        db: AsyncSession,
        movie_id: int,
        data: schemas.MovieRatingFromZeroToTen,
        user_profile: models.UserProfile
) -> dict[str, str] | MovieNotFoundError | Exception:

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    try:
        result_exist = await db.execute(select(models.MovieStar).filter(
            models.MovieStar.movie_id == movie.id,
            models.MovieStar.user_profile_id == user_profile.id
        )
        )
        existing_stars_rate = result_exist.scalar_one_or_none()
        if not existing_stars_rate:
            rate = models.MovieStar(
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


async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession,
        user_profile: models.UserProfile
) -> dict[str, models.Movie | bool] | MovieNotFoundError | Exception:

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id).options(
        selectinload(models.Movie.stars),
        selectinload(models.Movie.genres),
        selectinload(models.Movie.directors),

        selectinload(models.Movie.movie_comments).options(
            selectinload(models.MovieComment.movie_comment_replies).options(
                selectinload(models.MovieCommentReply.user_profile).options(
                    selectinload(models.UserProfile.user).joinedload(models.User.user_group)
                ),
            ),
            selectinload(models.MovieComment.user_profile).options(
                selectinload(models.UserProfile.user).joinedload(models.User.user_group)
            ),
        ),
        selectinload(models.Movie.movie_rate_in_stars),
        selectinload(models.Movie.movie_favorites),
        selectinload(models.Movie.movie_ratings),
        joinedload(models.Movie.certification)
    ))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        result_movie_user_star = await db.execute(select(models.MovieStar.rate).filter(
            models.MovieStar.user_profile_id == user_profile.id,
            models.MovieStar.movie_id == movie.id)
        )
        result_current_user_like_or_dislike = await db.execute(select(models.MovieRating.rating).filter(
            models.MovieRating.user_profile_id == user_profile.id,
            models.MovieRating.movie_id == movie.id)
        )
        result_count_of_likes = await db.execute(select(func.count().filter(
            models.MovieRating.rating == models.MovieRatingEnum.like))
        )

        result_count_of_dislikes = await db.execute(select(func.count()).filter(
            models.MovieRating.rating == models.MovieRatingEnum.dislike)
        )

        result_current_user_replies_ids = await db.execute(select(models.MovieCommentReply.id).filter(
            models.MovieCommentReply.user_profile_id == user_profile.id,
            models.MovieCommentReply.movie_comment.has(
                models.MovieComment.movie_id == movie.id
            )
        ))

        result_current_user_comment_ids = await db.execute(select(models.MovieComment.id).filter(
            models.MovieComment.user_profile_id == user_profile.id,
            models.MovieComment.movie_id == movie.id
        ))

        result_liked_comments_current_movie = await db.execute(select(models.MovieCommentLike.comment_id).filter(
            models.MovieCommentLike.user_profile_id == user_profile.id,
            models.MovieCommentLike.movie_comment.has(models.MovieComment.movie_id == movie.id)
        )
        )

        result_all_rates = await db.execute(select(models.MovieStar.rate).filter(models.MovieStar.movie_id == movie.id))
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


async def movie_create(
        db: AsyncSession,
        user_profile: models.UserProfile,
        data: schemas.MovieCreateSchema
) -> models.Movie | UserDontHavePermissionError | Exception:

    if user_profile.user.user_group.name is models.UserGroupEnum.user:
        raise UserDontHavePermissionError("User have not permissions to create new movies")

    import uuid
    movie_uuid = uuid.uuid4()
    try:
        result_genres = await db.execute(select(models.Genre).filter(models.Genre.id.in_(data.genre_ids)))
        genres = result_genres.scalars().all()

        result_stars = await db.execute(select(models.Star).filter(models.Star.id.in_(data.star_ids)))
        stars = result_stars.scalars().all()

        result_directors = await db.execute(select(models.Director).filter(models.Director.id.in_(data.director_ids)))
        directors = result_directors.scalars().all()

        new_movie = models.Movie(
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
        user_profile: models.UserProfile
) -> UserDontHavePermissionError | dict[str, str] | Exception:

    if user_profile.user.user_group.name is models.UserGroupEnum.user:
        raise UserDontHavePermissionError("User have not permissions to delete movies")

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    result_movie_in_users_cart = await db.execute(select(models.CartItem.id).filter(models.CartItem.movie_id == movie.id))
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
        user_profile: models.UserProfile,
        data: schemas.MovieUpdateScheme
):
    if user_profile.user.user_group.name in models.UserGroupEnum.user:
        raise UserDontHavePermissionError("User have no permissions for updating movies")

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")
    try:
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            if field not in ["genre_ids", "director_ids", "star_ids"]:
                setattr(movie, field, value)

        if data.genre_ids:
            result_genres = await db.execute(select(models.Genre).filter(models.Genre.id.in_(data.genre_ids)))
            movie.genres = result_genres.scalars().all()

        if data.director_ids:
            result_directors = await db.execute(
                select(models.Director).filter(models.Director.id.in_(data.director_ids)))
            movie.directors = result_directors.scalars().all()

        if data.star_ids:
            result_stars = await db.execute(select(models.Star).filter(models.Star.id.in_(data.star_ids)))
            movie.stars = result_stars.scalars().all()

        await db.commit()
        await db.refresh(movie)
        return movie
    except Exception as e:
        await db.rollback()
        raise e


# ----------------------------CART------------------


async def cart_add_item(
        db: AsyncSession,
        user_profile: models.UserProfile,
        movie_id: int,
        user_cart_id: int = None,
) -> MovieNotFoundError | UserDontHavePermissionError | dict[str, str]:

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    if not user_profile.cart:
        new_cart = models.Cart(user_profile_id=user_profile.id)
        db.add(new_cart)
        await db.commit()
        await db.refresh(new_cart)

    try:
        if user_profile.user.user_group.name == models.UserGroupEnum.user:
            cart = user_profile.cart
        else:
            if user_profile.user.user_group.name == models.UserGroupEnum.user:
                raise UserDontHavePermissionError("User have not permissions to add items to other user's carts")

            result_user_cart = await db.execute(select(models.Cart).filter(models.Cart.id == user_cart_id))
            cart = result_user_cart.scalar_one_or_none()

        all_movies_in_users_cart = [c.movie_id for c in cart.cart_items]
        result_all_purchased_movies_ids = await db.execute(select(models.CartItem.id).filter(
            models.CartItem.is_paid == True,
            models.CartItem.cart.has(
                models.Cart.user_profile == cart.user_profile_id
                )
            )
        )
        all_purchased_movies_ids = result_all_purchased_movies_ids.scalars().all()

        if movie.id in all_movies_in_users_cart or movie.id in all_purchased_movies_ids:
            raise MovieAlreadyIsPurchasedOrInCartError("Movie is already purchased or in user's cart")

        new_cart_item = CartItem(cart_id=cart.id, movie_id=movie.id)
        db.add(new_cart_item)
        await db.commit()
        await db.refresh(new_cart_item)
        return {"detail": "Item was successfully added"}

    except Exception as e:
        await db.rollback()
        raise e


async def cart_remove_item(
        db: AsyncSession,
        user_profile: models.UserProfile,
        movie_id: int,
        user_cart_id: int = None
) -> Exception | MovieNotFoundError | dict[str, str]:

    result_movie = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    if not user_cart_id:
        result_user_cart_item = await db.execute(select(models.CartItem).filter(
            models.CartItem.movie_id == movie.id, models.CartItem.cart.has(
            models.Cart.user_profile_id == user_profile.id)
            )
        )
    else:
        if user_profile.user.user_group.name == models.UserGroupEnum.user:
            raise UserDontHavePermissionError("User have not permissions to delete items from other user's carts")
        result_user_cart_item = await db.execute(select(models.CartItem).filter(
            models.CartItem.movie_id == movie.id, models.CartItem.cart.has(
            models.Cart.id == user_cart_id)
            )
        )

    user_cart_item = result_user_cart_item.scalar_one_or_none()

    if not user_cart_item:
        raise SomethingWentWrongError("User has not this movie in cart")

    try:
        await db.delete(user_cart_item)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e

    return {"detail": "Movie was successfully deleted from user's cart"}


async def cart_items_list(
        db: AsyncSession,
        user_profile: models.UserProfile,
        search_by_book_name: str = None
) -> dict[str, int | None | Cart | Any]:

    if not search_by_book_name:
        query = select(models.Cart).filter(
            models.Cart.user_profile_id == user_profile.id,
            models.Cart.cart_items.has(
                models.CartItem.is_paid != True
            )
        ).options(
            selectinload(models.Cart.cart_items).options(
                joinedload(models.CartItem.movie).options(
                    selectinload(models.Movie.genres),
                    selectinload(models.Movie.stars),
                    selectinload(models.Movie.directors),
                    joinedload(models.Movie.certification)
                ),
            )
        )
    else:
        query = select(models.Cart).filter(
            models.Cart.user_profile_id == user_profile.id,
            models.Cart.cart_items.has(
                models.CartItem.movie.has(
                    models.Movie.name.icontains(search_by_book_name)
                ),
                models.CartItem.is_paid != True
            )).options(
            selectinload(models.Cart.cart_items).options(
                joinedload(models.CartItem.movie).options(
                    selectinload(models.Movie.genres),
                    selectinload(models.Movie.stars),
                    selectinload(models.Movie.directors),
                    joinedload(models.Movie.certification)
                ),
            )
        )

    result_cart = await db.execute(query)
    cart = result_cart.scalar_one_or_none()

    result_total_price = await db.execute(
        select(func.sum(
            models.Movie.price)
        ).select_from(
            models.CartItem
        ).join(
            models.CartItem.cart
        ).join(
            models.CartItem.movie
        ).filter(
            models.Cart.user_profile_id == user_profile.id
        )
    )
    total_price = result_total_price.scalar_one_or_none()

    return {
        "cart_id": cart.id,
        "cart_items": cart.cart_items,
        "total_price": total_price or 0
    }


async def cart_purchased_items(
        db: AsyncSession,
        user_profile: models.UserProfile,
        search_by_book_name: str = None
) -> dict[str, int | None | Any]:

    if not search_by_book_name:
        query = select(models.Cart).filter(
            models.Cart.user_profile_id == user_profile.id,
            models.Cart.cart_items.has(
                models.CartItem.is_paid == True
            )
        ).options(
            selectinload(models.Cart.cart_items).options(
                joinedload(models.CartItem.movie).options(
                    selectinload(models.Movie.genres),
                    selectinload(models.Movie.stars),
                    selectinload(models.Movie.directors),
                    joinedload(models.Movie.certification)
                ),
            )
        )
    else:
        query = select(models.Cart).filter(
            models.Cart.user_profile_id == user_profile.id,
            models.Cart.cart_items.has(
                models.CartItem.movie.has(
                    models.Movie.name.icontains(search_by_book_name)
                ),
                models.CartItem.is_paid == True
            )).options(
            selectinload(models.Cart.cart_items).options(
                joinedload(models.CartItem.movie).options(
                    selectinload(models.Movie.genres),
                    selectinload(models.Movie.stars),
                    selectinload(models.Movie.directors),
                    joinedload(models.Movie.certification)
                ),
            )
        )

    result_cart = await db.execute(query)
    cart = result_cart.scalar_one_or_none()
    return {
        "cart_id": cart.id,
        "cart_items": cart.cart_items
    }


async def admin_carts_list(
        db: AsyncSession,
        user_profile: models.UserProfile,
        search_by_user_email: str = None,
        skip: int = 0,
        limit: int = 20
) -> Sequence[models.Cart]:
    if user_profile.user.user_group.name == models.UserGroupEnum.user:
        raise UserDontHavePermissionError("Users have not permissions to visit this page.")

    if search_by_user_email:
        query = select(models.Cart).filter(
            models.Cart.user_profile.has(
                models.UserProfile.user.has(
                    models.User.email == search_by_user_email
                ))
        ).options(
            selectinload(models.Cart.cart_items),
            joinedload(models.Cart.user_profile).options(
                joinedload(models.UserProfile.user)
            )
        ).offset(skip=skip).limit(limit=limit)
    else:
        query = select(models.Cart).options(
            selectinload(models.Cart.cart_items),
            joinedload(models.Cart.user_profile).options(
                joinedload(models.UserProfile.user)
            )
        ).offset(skip=skip).limit(limit=limit)

    result_carts = await db.execute(query)
    return result_carts.scalars().all()


async def admin_user_cart_detail(
        db: AsyncSession,
        user_profile: models.UserProfile,
        user_cart_id: int,
):
    if user_profile.user.user_group == models.UserGroupEnum.user:
        raise UserDontHavePermissionError

    result_cart = await db.execute(select(models.Cart).filter(models.Cart.id == user_cart_id).options(
        selectinload(models.Cart.cart_items).options(
            joinedload(models.CartItem.movie).options(
                selectinload(models.Movie.genres),
                selectinload(models.Movie.stars),
                selectinload(models.Movie.directors),
                joinedload(models.Movie.certification)
            ),
        ),
        joinedload(models.Cart.user_profile).options(
            joinedload(models.UserProfile.user)
        )
    ))
    cart = result_cart.scalar_one_or_none()

    if not cart:
        raise CartNotExistError("Cart by provided id does not exists")

    return cart


# -------------------------------------------------- ORDER

async def order_list(
        db: AsyncSession,
        user_profile: models.UserProfile,
        offset: int = 0,
        limit: int = 20
) -> Sequence[models.Order]:

    result_all_orders = await db.execute(select(models.Order).filter(
        models.Order.user_profile_id == user_profile.id).options(
        joinedload(models.Order.user_profile).options(
            joinedload(models.UserProfile.user)
        ),
        selectinload(models.Order.order_items).options(
            joinedload(models.OrderItem.movie).options(
                selectinload(models.Movie.genres),
                selectinload(models.Movie.stars),
                selectinload(models.Movie.directors)
            )
        )
    ).offset(offset).limit(limit))
    all_orders = result_all_orders.scalars().all()
    total_items = len(all_orders)

    return {"all_orders": all_orders, "total_items": total_items}


async def order_detail(
        db: AsyncSession,
        user_profile: models.UserProfile,
        order_id: int
) -> models.Order | OrderDoesNotExistError:

    result_order = await db.execute(select(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_profile_id == user_profile.id).options(
            joinedload(models.Order.user_profile).options(
                joinedload(models.UserProfile.user)
            ),
            selectinload(models.Order.order_items).options(
                joinedload(models.OrderItem.movie).options(
                    selectinload(models.Movie.genres),
                    selectinload(models.Movie.directors),
                    selectinload(models.Movie.stars)
                )
            )

        )
    )
    order = result_order.scalar_one_or_none()

    if not order:
        raise OrderDoesNotExistError("Order was not found")

    return order


async def create_order(
        db: AsyncSession,
        user_profile: models.UserProfile,
) -> models.Order | Exception:

    result_user_items_price = await db.execute(
        select(func.sum(models.Movie.price))
        .select_from(models.CartItem)
        .join(models.CartItem.movie)
        .join(models.CartItem.cart)
        .filter(models.Cart.user_profile_id == user_profile.id)
    )
    result_user_items = await db.execute(select(CartItem).filter(
        models.CartItem.cart.has(
            models.Cart.user_profile_id == user_profile.id,
            ),
        models.CartItem.is_paid == False
        ).options(
        joinedload(models.CartItem.movie)
        )
    )
    user_items = result_user_items.scalars().all()
    total_amount = result_user_items_price.scalar_one_or_none() or 0.00
    try:
        new_order = models.Order(
            user_profile_id=user_profile.id,
            total_amount=total_amount
        )
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)

        order_items = [models.OrderItem(
            order_id=new_order.id,
            movie_id=item.movie_id,
            price_at_order=item.movie.price
        ) for item in user_items]

        if order_items:
            db.add_all(order_items)
            await db.commit()

        return new_order
    except Exception as e:
        await db.rollback()
        raise e


async def order_confirm(
        db: AsyncSession,
        user_profile: models.UserProfile,
        order_id: int
) -> OrderDoesNotExistError | dict[str, str]:
    result_order = await db.execute(select(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_profile_id == user_profile.id)
    )
    order = result_order.scalar_one_or_none()

    if not order:
        raise OrderDoesNotExistError("Order by provided id does not exists")

    ### LOGIC STRIPE
    return {"detail": "redirect_to_stripe_url"}


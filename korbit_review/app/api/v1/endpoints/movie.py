from typing import List

from fastapi import APIRouter, BackgroundTasks
from starlette import status
from starlette.responses import JSONResponse

from app.crud.movie import read_movies, get_movie_by_id, create_comment, delete_movie, update_movie, movie_create, \
    delete_comment, reply_comment, like_comment_or_delete_if_exists, like_comment_reply_or_delete_if_exists, \
    add_movie_to_favorite_or_delete_if_exists, like_or_dislike_movie_and_delete_if_exists, \
    rate_movie_from_0_to_10_or_delete_rate_if_exists
from app.models.movie import MovieComment, MovieCommentReply, Movie
from app.schemas.movie import MovieRead, MovieReadDetail, CommentCreateSchema, CommentReadAfterCreationSchema, \
    MovieRatingFromZeroToTen, UserMovieRating, MovieCommentReplyCreate, MovieCommentReplyCreatedRead, MovieCreateSchema, \
    MovieUpdateScheme
from app.utils.dependencies import DpGetDB, GetCurrentUser
from app.utils.exceptions import SomethingWentWrongError

router = APIRouter()


@router.get("/movies/", response_model=List[MovieRead])
async def movies_list_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
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
    filtered_movies = await read_movies(
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


@router.get("/movies/{movie_id}/", response_model=MovieReadDetail)
async def movie_detail_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser
) -> MovieReadDetail:

    movie_dict = await get_movie_by_id(
        movie_id=movie_id,
        db=db,
        user_profile=user.user_profile
    )
    movie_detail = MovieReadDetail.model_validate(movie_dict.get("movie"))
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


@router.delete("/movies/{movie_id}/delete/")
async def movie_delete_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser
) -> JSONResponse:
    deleted_movie = await delete_movie(movie_id=movie_id, db=db, user_profile=user.user_profile)

    if not isinstance(deleted_movie, dict):
        raise SomethingWentWrongError

    if deleted_movie.get("detail") == "Movie was successfully deleted.":
        return JSONResponse(content=f"{deleted_movie.get('detail')}", status_code=status.HTTP_200_OK)

    return JSONResponse(content=f"{deleted_movie.get('detail')}", status_code=status.HTTP_403_FORBIDDEN)

@router.patch("/movies/{movie_id}/update/", response_model=MovieRead)
async def movie_update_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser,
        data: MovieUpdateScheme
) ->Movie:
    updated_movie = await update_movie(movie_id=movie_id, db=db, user_profile=user.user_profile, data=data)

    if not isinstance(updated_movie, Movie):
        raise SomethingWentWrongError

    return updated_movie


@router.post("/movies/create/", response_model=MovieReadDetail)
async def movie_create_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        data: MovieCreateSchema
) -> Movie:
    created_movie = await movie_create(db=db, user_profile=user.user_profile, data=data)

    if not isinstance(created_movie, Movie):
        raise SomethingWentWrongError

    return created_movie


@router.post("/movies/{movie_id}/create_comment/", response_model=CommentReadAfterCreationSchema)
async def movie_create_comment_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser,
        data: CommentCreateSchema
) -> MovieComment:
    created_comment = await create_comment(
        movie_id=movie_id,
        db=db,
        user_profile=user.user_profile,
        data=data
    )

    if not isinstance(created_comment, MovieComment):
        raise SomethingWentWrongError

    return created_comment


@router.delete("/movies/comments/{comment_id}/delete_comment/")
async def movie_delete_comment_endpoint(
        comment_id: int,
        db: DpGetDB,
        user: GetCurrentUser
) -> JSONResponse:
    deleted_comment = await delete_comment(comment_id=comment_id, db=db, user_profile=user.user_profile)

    if not isinstance(deleted_comment, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{deleted_comment.get('detail')}", status_code=status.HTTP_200_OK)


@router.post("/movies/comments/{comment_id}/comment_reply_create/", response_model=MovieCommentReplyCreatedRead)
async def movie_comment_reply_endpoint(
        comment_id: int,
        db: DpGetDB,
        user: GetCurrentUser,
        data: MovieCommentReplyCreate,
        background_task: BackgroundTasks
) -> MovieCommentReply:
    created_reply = await reply_comment(
        comment_id=comment_id,
        db=db,
        user_profile=user.user_profile,
        data=data,
        background_task=background_task
    )
    if not isinstance(created_reply, MovieCommentReply):
        raise SomethingWentWrongError

    return created_reply


@router.post("/movies/comments/{comment_id}/like_or_delete_like/")
async def movie_comment_like_or_delete_like_if_exists_endpoint(
        comment_id: int,
        db: DpGetDB,
        user: GetCurrentUser
) -> JSONResponse:
    like_or_delete_like = await like_comment_or_delete_if_exists(
        comment_id=comment_id,
        db=db,
        user_profile=user.user_profile
    )

    if not isinstance(like_or_delete_like, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{like_or_delete_like.get('detail')}", status_code=status.HTTP_200_OK)


@router.post("/movies/comments/comment_replies/{reply_id}/like_or_delete_like/")
async def movie_comment_reply_like_or_delete_like_if_exists_endpoint(
        reply_id: int,
        db: DpGetDB,
        user: GetCurrentUser
) -> JSONResponse:
    comment_like_or_unlike = await like_comment_reply_or_delete_if_exists(
        comment_reply_id=reply_id,
        db=db,
        user_profile=user.user_profile
    )

    if not isinstance(comment_like_or_unlike, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{comment_like_or_unlike.get('detail')}", status_code=status.HTTP_200_OK)


@router.post("/movies/{movie_id}/add_to_favorite_or_delete/")
async def movie_add_to_favorite_or_delete_if_exists_endpoint(
        movie_id: int,
        user: GetCurrentUser,
        db: DpGetDB
) -> JSONResponse:
    add_to_favorite_or_delete = await add_movie_to_favorite_or_delete_if_exists(
        movie_id=movie_id,
        user_profile=user.user_profile,
        db=db
    )

    if not isinstance(add_to_favorite_or_delete, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{add_to_favorite_or_delete.get('detail')}", status_code=status.HTTP_200_OK)


@router.post("/movies/{movie_id}/like_or_dislike_or_delete/")
async def movie_like_or_dislike_or_delete_like_or_dislike_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser,
        data: UserMovieRating
) -> JSONResponse:
    like_or_dislike_or_delete = await like_or_dislike_movie_and_delete_if_exists(
        movie_id=movie_id,
        user_profile=user.user_profile,
        db=db,
        data=data
    )

    if not isinstance(like_or_dislike_or_delete, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{like_or_dislike_or_delete.get('detail')}", status_code=status.HTTP_200_OK)


@router.post("/movies/{movie_id}/rate_from_zero_to_ten/")
async def movie_rate_from_sero_to_ten_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser,
        data: MovieRatingFromZeroToTen
) -> JSONResponse:
    rate_movie = await rate_movie_from_0_to_10_or_delete_rate_if_exists(
        db=db,
        movie_id=movie_id,
        data=data,
        user_profile=user.user_profile
    )
    if not isinstance(rate_movie, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{rate_movie.get('detail')}", status_code=status.HTTP_200_OK)

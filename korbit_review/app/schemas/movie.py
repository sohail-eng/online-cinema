from decimal import Decimal
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, UUID4

from app.schemas.user import UserProfileRead


class CommentReadAfterCreationSchema(BaseModel):
    id: int
    user_profile_id: int
    movie_id: int
    text: str


class CommentCreateSchema(BaseModel):
    text: str = Field(max_length=500)


class LikeOrDislikeEnum(str, Enum):
    like = "LIKE"
    dislike = "DISLIKE"


class UserMovieRating(BaseModel):
    rating: LikeOrDislikeEnum


class MovieRatingFromZeroToTen(BaseModel):
    rate: int = Field(ge=0, le=10)


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# M2M
class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(
        from_attributes=True
    )


# M2M
class StarsSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(
        from_attributes=True
    )


class DirectorsSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(
        from_attributes=True
    )


class MovieCommentReplyCreate(BaseModel):
    votes: Optional[int] = 0
    comment_id: int
    user_profile_id: int
    text: str = Field(max_length=500)


class MovieCommentReplyCreatedRead(MovieCommentReplyCreate):
    id: int


class MovieCommentReply(BaseModel):
    id: int
    votes: Optional[int] = 0
    comment_id: int
    user_profile: UserProfileRead
    text: str = Field(max_length=500)

    model_config = ConfigDict(
        from_attributes=True
    )


class MovieComments(BaseModel):
    id: int
    text: str
    user_profile: UserProfileRead
    movie_comment_replies: List[MovieCommentReply]

    model_config = ConfigDict(
        from_attributes=True
    )

class MovieBase(BaseModel):
    name: str
    year: int
    time: int
    imdb: float
    image: Optional[str] = None
    votes: int
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: str
    price: Optional[Decimal] = None


class MovieOrderItemView(MovieBase):
    genres: List[GenreSchema]
    uuid: UUID4
    stars: List[StarsSchema]
    directors: List[DirectorsSchema]

    model_config = ConfigDict(
        from_attributes=True
    )


class MovieCreateSchema(MovieBase):
    certification_id: int
    genre_ids: List[int]
    star_ids: List[int]
    director_ids: List[int]


class MovieRead(MovieBase):
    id: int
    uuid: UUID4
    certification: Optional[CertificationSchema] = None

    #custom
    count_of_comments: int = 0
    count_of_ratings: int = 0
    count_of_favorites: int = 0
    average_rate_in_stars: float = 0

    #m2m
    genres: List[GenreSchema] = []
    stars: List[StarsSchema] = []
    directors: List[DirectorsSchema] = []

    model_config = ConfigDict(
        from_attributes=True
    )


class MovieReadDetail(MovieBase):
    id: int
    uuid: UUID4
    certification: Optional[CertificationSchema] = None

    #custom
    in_favorite_by_current_user: Optional[bool] = None
    current_user_star_rating: Optional[int] = None
    current_user_like_or_dislike: Optional[str] = None
    liked_comments_current_movie_ids: Optional[list[int]] = None
    count_of_likes_current_movie: Optional[int] = None
    count_of_dislikes_current_movie: Optional[int] = None
    current_user_comment_ids: Optional[list[int]] = None
    current_user_replies_ids: Optional[list[int]] = None
    average_rate_in_stars: Optional[float] = 0
    count_of_comments: Optional[int] = 0
    count_of_ratings: Optional[int] = 0
    count_of_favorites: Optional[int] = 0

    is_favorite: bool = False

    #o2m
    movie_comments: List[MovieComments] = []

    #m2m
    genres: List[GenreSchema] = []
    stars: List[StarsSchema] = []
    directors: List[DirectorsSchema] = []

    model_config = ConfigDict(
        from_attributes=True
    )


class MovieUpdateScheme(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    time: Optional[int] = None
    imdb: Optional[float] = None
    image: Optional[str] = None
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    certification_id: Optional[int] = None

    genre_ids: Optional[List[int]] = None
    star_ids: Optional[List[int]] = None
    director_ids: Optional[List[int]] = None


class MovieCartRead(BaseModel):
    id: int
    uuid: UUID4
    name: str
    year: int
    time: int
    price: Decimal
    image: str

    genres: List[GenreSchema]
    stars: List[StarsSchema]
    directors: List[DirectorsSchema]

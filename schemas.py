import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List

import pydantic
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict, model_validator, Field
from pydantic import UUID4


class TokenPayload(BaseModel):
    email: EmailStr


class LoginTokens(BaseModel):
    access_token: str
    header: Optional[str] = "bearer"


class AccessToken(BaseModel):
    access_token: str

class UserGroup(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(
        from_attributes=True
    )


class UserBase(BaseModel):
    email: EmailStr

class UserCreated(UserBase):
    id: int
    group: UserGroup

    model_config = ConfigDict(
        from_attributes=True
    )

class UserRead(UserBase):
    id: int
    user_group: UserGroup

    model_config = ConfigDict(
        from_attributes=True
    )


class GenderEnum(str, Enum):
    man = "MAN"
    woman = "WOMAN"


class UserProfileRead(BaseModel):
    id: int
    user: UserRead
    first_name: Optional[str] = Field(max_length=60, default=None)
    last_name: Optional[str] = Field(max_length=60, default=None)
    avatar: Optional[str] = Field(max_length=300, default=None)
    gender: Optional[GenderEnum]
    date_of_birth: Optional[datetime.date] = None
    info: Optional[str] = Field(max_length=200)

    model_config = ConfigDict(
        from_attributes=True
    )


class CreateUserForm(UserBase):
    password: str
    group_id: int

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str):
        if len(password) < 8 or password.isnumeric() or password.isalpha():
            raise pydantic.ValidationError("Password must contain at least 8 symbols, also not only digits or numbers.")
        return password


class SendNewActivationTokenSchema(BaseModel):
    email: EmailStr

class ChangePasswordRequestSchema(BaseModel):
    email: EmailStr

class NewPasswordDataSchema(BaseModel):
    password1: str
    password2: str

    @model_validator(mode="after")
    def passwords_validate(self):
        password1 = self.password1
        password2 = self.password2

        if password1 != password2:
            raise pydantic.ValidationError("Passwords are not equal")

        if password1.isalpha() or password1.isnumeric() or len(password1) < 8:
            return pydantic.ValidationError("Password must contain not only digits or numbers and must be longer than 8 characters")

        return self


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

# ----------------------------------------------- CART

# users cart
class CartItemsReadSchema(BaseModel):
     id: int
     cart_id: int
     movie_id: int
     added_at: int
     is_paid: bool

     movie: MovieCartRead

     model_config = ConfigDict(
         from_attributes=True
     )

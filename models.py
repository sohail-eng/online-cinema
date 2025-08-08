from enum import Enum

from sqlalchemy import Column, DECIMAL, Integer, ForeignKey, String, Enum as SqlEnum, Boolean, DateTime, func, Date, \
    Float, Text, UniqueConstraint, Table
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class UserGroupEnum(str, Enum):
    user = "USER"
    moderator = "MODERATOR"
    admin = "ADMIN"

class GenderEnum(str, Enum):
    man = "MAN"
    woman = "WOMAN"


class UserGroup(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(SqlEnum(UserGroupEnum), unique=True, nullable=False)

    users = relationship("User", back_populates="user_group")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(150), nullable=False)
    is_active = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    group_id = Column(Integer, ForeignKey("user_groups.id"))

    user_group = relationship("UserGroup", back_populates="users")
    user_profile = relationship("UserProfile", back_populates="user", uselist=False)
    activation_token = relationship("ActivationToken", back_populates="user", uselist=False)
    password_reset_token = relationship("PasswordResetToken", back_populates="user", uselist=False)
    refresh_token = relationship("RefreshToken", back_populates="user", uselist=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    first_name = Column(String(60), nullable=True)
    last_name = Column(String(60), nullable=True)
    avatar = Column(String(300), nullable=True)
    gender = GenderEnum
    date_of_birth = Column(Date, nullable=True)
    info = Column(String(200), nullable=True)

    user = relationship("User", back_populates="user_profile")


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String(100), unique=True)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="activation_token")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String(300), unique=True)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="password_reset_token")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String(300), unique=True)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="refresh_token")


# ------------------------- MOVIE-MODELS-----------------

movie_genres = Table(
    "movie_genres", Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id"), primary_key=True)
)

class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)

    movies = relationship("Movie", secondary=movie_genres, back_populates="genres")


movie_stars = Table(
    "movie_stars", Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("stars_id", Integer, ForeignKey("stars.id"), primary_key=True)
    )

class Star(Base):
    __tablename__ = "stars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)

    movies = relationship("Movie", secondary=movie_stars, back_populates="stars")


movie_directors = Table(
    "movie_directors", Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("director_id", Integer, ForeignKey("directors.id"), primary_key=True)
)

class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)

    movies = relationship("Movie", secondary=movie_directors, back_populates="directors")


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)

    movies = relationship("Movie", back_populates="certification")


class Movie(Base):
    __tablename__ = "movies"

    __table_args__ = (
        UniqueConstraint("name", "year", "time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(200), unique=True)
    name = Column(String(200), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    time = Column(Integer, nullable=False)
    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score = Column(Float, nullable=True)
    gross = Column(Float, nullable=True)
    description = Column(Text(1000), nullable=False)
    price = Column(DECIMAL(13, 2), nullable=True)
    certification_id = Column(Integer, ForeignKey("certifications.id"))

    certification = relationship("Certification", back_populates="movies")

    genres = relationship("Genre", secondary=movie_genres, back_populates="movies")
    stars = relationship("Star", secondary=movie_stars, back_populates="movies")
    directors = relationship("Director", secondary=movie_directors, back_populates="movies")


class MovieRatingEnum(str, Enum):
    like = "like"
    dislike = "dislike"

# Like and Dislike
class MovieRating(Base):
    __tablename__ = "movie_rating"

    __table_args__ = (
        UniqueConstraint("user_profile_id", "movie_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"))
    movie_id = Column(Integer, ForeignKey("movies.id"))
    rating = Column(SqlEnum(MovieRatingEnum))

    user_profile = relationship("UserProfile", back_populates="movie_ratings")
    movie = relationship("Movie", back_populates="movie_ratings")


class MovieComment(Base):
    __tablename__ = "movie_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"))
    movie_id = Column(Integer, ForeignKey("movies.id"))
    text = Column(String(500), nullable=False)

    movie_comment_likes = relationship("MovieCommentLike", back_populates="movie_comment")
    movie_comment_replies = relationship("MovieCommentReply", back_populates="movie_comment")

    user_profile = relationship("UserProfile", back_populates="movie_comments")
    movie = relationship("Movie", back_populates="movie_comments")

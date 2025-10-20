from enum import Enum

from sqlalchemy.orm import relationship

from app.db.database import Base

from sqlalchemy import Column, DECIMAL, Integer, ForeignKey, String, Enum as SqlEnum, \
    Float, Text, UniqueConstraint, Table


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
    image = Column(String(500), nullable=True)
    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score = Column(Float, nullable=True)
    gross = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    price = Column(DECIMAL(13, 2), nullable=True)
    certification_id = Column(Integer, ForeignKey("certifications.id"))

    certification = relationship("Certification", back_populates="movies")

    movie_ratings = relationship("MovieRating", back_populates="movie")
    movie_comments = relationship("MovieComment", back_populates="movie")
    movie_favorites = relationship("MovieFavorite", back_populates="movie")
    movie_rate_in_stars = relationship("MovieStar", back_populates="movie")
    cart_items = relationship("CartItem", back_populates="movie")

    genres = relationship("Genre", secondary=movie_genres, back_populates="movies")
    stars = relationship("Star", secondary=movie_stars, back_populates="movies")
    directors = relationship("Director", secondary=movie_directors, back_populates="movies")


    @property
    def count_of_comments(self) -> int:
        return len(self.movie_comments)

    @property
    def count_of_ratings(self) -> int:
        return len(self.movie_ratings)

    @property
    def count_of_favorites(self) -> int:
        return len(self.movie_favorites)

    @property
    def average_rate_in_stars(self) -> float:
        all_rates = [i.rate for i in self.movie_rate_in_stars]
        if not all_rates:
            return 0.0

        sum_of_all_rates = sum(all_rates)
        length = len(all_rates)

        return sum_of_all_rates / length


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
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"))
    rating = Column(SqlEnum(MovieRatingEnum))

    user_profile = relationship("UserProfile", back_populates="movie_ratings")
    movie = relationship("Movie", back_populates="movie_ratings")


class MovieComment(Base):
    __tablename__ = "movie_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    votes = Column(Integer, nullable=True, default=0)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"))
    text = Column(String(500), nullable=False)

    movie_comment_likes = relationship("MovieCommentLike", back_populates="movie_comment", cascade="all, delete-orphan")
    movie_comment_replies = relationship("MovieCommentReply", back_populates="movie_comment", cascade="all, delete-orphan")

    user_profile = relationship("UserProfile", back_populates="movie_comments")
    movie = relationship("Movie", back_populates="movie_comments")


class MovieCommentLike(Base):
    __tablename__ = "movie_comment_likes"

    __table_args__ = (
        UniqueConstraint("comment_id", "user_profile_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("movie_comments.id", ondelete="CASCADE"))
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))

    user_profile = relationship("UserProfile", back_populates="movie_comment_likes")
    movie_comment = relationship("MovieComment", back_populates="movie_comment_likes")


class MovieCommentReply(Base):
    __tablename__ = "movie_comment_replies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("movie_comments.id", ondelete="CASCADE"))
    votes = Column(Integer, nullable=True, default=0)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    text = Column(String(500), nullable=False)

    movie_comment = relationship("MovieComment", back_populates="movie_comment_replies")
    user_profile = relationship("UserProfile", back_populates="movie_comment_replies")


class MovieFavorite(Base):
    __tablename__ = "movie_favorites"

    __table_args__ = (
        UniqueConstraint("movie_id", "user_profile_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"))
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))

    movie = relationship("Movie", back_populates="movie_favorites")
    user_profile = relationship("UserProfile", back_populates="movie_favorites")


class MovieStar(Base):
    __tablename__ = "movie_rate_in_stars"

    __table_args__ = (
        UniqueConstraint("user_profile_id", "movie_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"))
    rate = Column(Integer, nullable=False)

    movie = relationship("Movie", back_populates="movie_rate_in_stars")
    user_profile = relationship("UserProfile", back_populates="movie_rate_in_stars")

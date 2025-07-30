import enum
import uuid
from sqlalchemy import Table, Column, ForeignKey, Integer, String, Float, Text, DECIMAL, UniqueConstraint, Enum
from sqlalchemy.orm import relationship

from .base import Base
from .users import UserFavoriteMovie

MovieGenres = Table(
    "movie_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True, nullable=False
    ),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True, nullable=False
    ),
)

MovieStars = Table(
    "movie_stars",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True, nullable=False
    ),
    Column(
        "star_id",
        ForeignKey("stars.id", ondelete="CASCADE"),
        primary_key=True, nullable=False
    ),
)


MovieDirectors = Table(
    "movie_directors",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True, nullable=False),
    Column(
        "director_id",
        ForeignKey("directors.id", ondelete="CASCADE"),
        primary_key=True, nullable=False),
)


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    movies = relationship(
        "Movie",
        secondary=MovieGenres,
        back_populates="genres",
    )


class Star(Base):
    __tablename__ = "stars"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    movies = relationship(
        "Movie",
        secondary=MovieStars,
        back_populates="stars",
    )


class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    movies = relationship(
        "Movie",
        secondary=MovieDirectors,
        back_populates="directors",
    )


class Certification(Base):
    __tablename__ = "certification"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    movies = relationship(
        "Movie",
        back_populates="certification",
    )


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True)
    uuid = Column(String, nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score = Column(Float, nullable=True)
    gross = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    certification_id = Column(Integer, ForeignKey("certification.id"), nullable=False)

    certification = relationship(
        "Certification",
        back_populates="movies",
    )
    genres = relationship(
        "Genre",
        secondary=MovieGenres,
        back_populates="movies",
    )
    stars = relationship(
        "Star",
        secondary=MovieStars,
        back_populates="movies",
    )
    directors = relationship(
        "Director",
        secondary=MovieDirectors,
        back_populates="movies",
    )
    likes = relationship(
        "MovieLike",
        back_populates="movies",
        cascade="all, delete-orphan"
    )
    users_favorite_movies = relationship(
        "User",
        secondary=UserFavoriteMovie,
        back_populates="favorite_movies"
    )
    ratings = relationship(
        "MovieRating",
        back_populates="movie",
        cascade="all, delete-orphan"
    )
    cart_items = relationship("CartItem", back_populates="cart_items")

    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="unique_movie_constraint"),
    )


class LikeStatusEnum(str, enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"


class MovieLike(Base):
    __tablename__ = "movie_likes"

    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True)
    like_status = Column(Enum(LikeStatusEnum), nullable=False)

    movies = relationship("Movie", back_populates="likes")
    user = relationship("User", back_populates="likes")

    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="unique_user_movie_like"),)


class MovieRating(Base):
    __tablename__ = "movie_ratings"

    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True)
    rating = Column(Integer, nullable=False)

    user = relationship("User", back_populates="ratings")
    movie = relationship("Movie", back_populates="ratings")

    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="unique_user_movie_rating"),)

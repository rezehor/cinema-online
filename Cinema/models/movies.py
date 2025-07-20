from sqlalchemy import Table, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from Cinema.database import Base

MoviesGenres = Table(
    "movies_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True, nullable=False),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True, nullable=False),
)

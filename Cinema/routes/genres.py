from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from Cinema.database import get_db
from Cinema.models import Genre, MovieGenres
from Cinema.schemas.movies import GenreListResponseSchema, GenreWithCountSchema

router = APIRouter()


@router.get("/", response_model=GenreListResponseSchema)
async def get_genres_with_movie_count(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Genre.id, Genre.name, func.count(MovieGenres.c.movie_id).label("movie_count"))
        .join(MovieGenres, MovieGenres.c.genre_id == Genre.id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    result = await db.execute(stmt)
    genres = result.all()

    genre_list = [
        GenreWithCountSchema(id=genre.id, name=genre.name, movie_count=genre.movie_count)
        for genre in genres
    ]

    return GenreListResponseSchema(genres=genre_list)

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from Cinema.config.dependencies import get_current_user
from Cinema.database import get_db
from Cinema.models import User, Movie, Star, Director, Genre
from Cinema.models.users import UserFavoriteMovie
from Cinema.routes.movies import MovieSortByEnum, SortOrderEnum
from Cinema.schemas.movies import MovieListResponseSchema, MovieListItemSchema
from Cinema.schemas.users import MessageResponseSchema

router = APIRouter()


@router.post(
    "/{movie_id}",
    summary="Add a movie to favorites",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponseSchema
)
async def add_movie_to_favorites(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
) -> MessageResponseSchema:
    movie = (await db.execute(select(Movie).where(Movie.id == movie_id))).scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    if movie in current_user.favorite_movies:
        raise HTTPException(
            status_code=400,
            detail=f"{movie.name} is already in your favorites."
        )

    current_user.favorite_movies.append(movie)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while adding the movie to favorites."
        )

    return MessageResponseSchema(message=f"{movie.name} added to favorites")


@router.delete(
    "/{movie_id}",
    summary="Remove a movie from favorites",
    status_code=status.HTTP_204_NO_CONTENT
)
async def remove_movie_from_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Movie).join(UserFavoriteMovie).where(
        Movie.id == movie_id,
        UserFavoriteMovie.c.user_id == current_user.id
    )
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found in your favorites."
        )

    current_user.favorite_movies.remove(movie)
    await db.commit()



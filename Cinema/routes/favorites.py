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


@router.get(
    "/",
    response_model=MovieListResponseSchema,
    summary="List, filter, sort, and search favorite movies"
)
async def get_favorite_movies(
        page: int = Query(1, ge=1, description="Page number"),
        per_page: int = Query(10, ge=1, le=20, description="Number of movies per page"),
        db: AsyncSession = Depends(get_db),
        # Filtering parameters
        year: Optional[int] = Query(None, description="Filter by release year"),
        imdb: Optional[float] = Query(None, ge=0, le=10, description="Filter by imdb rating"),
        genre: Optional[str] = Query(None, description="Filter by genre name"),
        # Sorting parameters
        sort_by: Optional[MovieSortByEnum] = Query(None, description="Attribute to sort movies by"),
        sort_order: SortOrderEnum = Query(SortOrderEnum.desc, description="Sort order: 'asc' or 'desc'"),
        # Searching parameters
        search: Optional[str] = Query(
            None,
            description="Search by movie title, description, star, or director name"
        ),
        current_user: User = Depends(get_current_user)
):
    stmt = (select(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.stars),
        selectinload(Movie.directors)
    ).join(UserFavoriteMovie)
            .where(UserFavoriteMovie.c.user_id == current_user.id))

    if year:
        stmt = stmt.filter(Movie.year == year)
    if imdb:
        stmt = stmt.where(Movie.imdb >= imdb)
    if genre:
        stmt = stmt.join(Movie.genres).where(func.lower(Genre.name) == genre.lower())

    if sort_by:
        sort_column = getattr(Movie, sort_by.value)
        if sort_order == SortOrderEnum.desc:
            stmt = stmt.order_by(sort_column.desc())
        stmt = stmt.order_by(sort_column.asc())

    if search:
        search_term = f"%{search.lower()}%"
        stmt = stmt.join(Movie.stars).join(Movie.directors).where(
            or_(
                func.lower(Movie.name).like(search_term),
                func.lower(Movie.description).like(search_term),
                func.lower(Star.name).like(search_term),
                func.lower(Director.name).like(search_term)
            )
        )

    offset = (page - 1) * per_page
    count_stmt = select(func.count(Movie.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found.")

    stmt = stmt.offset(offset).limit(per_page)

    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().unique().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]

    total_pages = (total_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=f"/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response

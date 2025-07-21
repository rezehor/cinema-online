from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from Cinema.database import get_db
from Cinema.models import Movie
from Cinema.schemas.movies import MovieListResponseSchema, MovieListItemSchema, MovieDetailSchema

router = APIRouter()


@router.get("/", response_model=MovieListResponseSchema)
async def get_movies(
        page: int = Query(1, ge=1, description="Page number"),
        per_page: int = Query(10, ge=1, le=20, description="Number of movies per page"),
        db: AsyncSession = Depends(get_db)
) -> MovieListResponseSchema:
    offset = (page - 1) * per_page
    count_stmt = select(func.count(Movie.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found.")

    stmt = select(Movie)
    stmt = stmt.offset(offset).limit(per_page)

    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()

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


@router.get("/{movie_id}", response_model=MovieDetailSchema)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    stmt = (select(Movie)
            .options(
        joinedload(Movie.genres),
        joinedload(Movie.stars),
        joinedload(Movie.directors),
        joinedload(Movie.certification))
            .where(Movie.id == movie_id)
            )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    return MovieDetailSchema.model_validate(movie)


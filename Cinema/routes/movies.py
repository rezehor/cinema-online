from enum import Enum
from typing import Optional
from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from Cinema.config.dependencies import get_current_user
from Cinema.database import get_db
from Cinema.models import Movie, Certification, Genre, Star, Director, User
from Cinema.models.movies import MovieLike, LikeStatusEnum
from Cinema.schemas.movies import MovieListResponseSchema, MovieListItemSchema, MovieDetailSchema, MovieCreateSchema, \
    MovieUpdateSchema, MovieLikeResponseSchema, MovieLikeRequestSchema

router = APIRouter()

class MovieSortByEnum(str, Enum):
    year = "year"
    imdb = "imdb"
    votes = "votes"

class SortOrderEnum(str, Enum):
    asc = "asc"
    desc = "desc"

@router.get("/", response_model=MovieListResponseSchema)
async def get_movies(
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
        )
) -> MovieListResponseSchema:
    stmt = select(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.stars),
        selectinload(Movie.directors)
    )
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


async def get_movie_like_stats(movie_id: int, db: AsyncSession):
    stmt = (
        select(
            func.count().filter(MovieLike.like_status == LikeStatusEnum.LIKE),
            func.count().filter(MovieLike.like_status == LikeStatusEnum.DISLIKE)
        )
        .where(MovieLike.movie_id == movie_id)
    )
    result = await db.execute(stmt)
    likes, dislikes = result.one()
    return likes, dislikes

@router.get("/{movie_id}", response_model=MovieDetailSchema)
async def get_movie_by_id(
    movie_id: int,
    db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    stmt = (
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.certification),
        )
        .where(Movie.id == movie_id)
    )
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    likes, dislikes = await get_movie_like_stats(movie_id, db)

    return MovieDetailSchema.model_validate({
        **movie.__dict__,
        "genres": movie.genres,
        "stars": movie.stars,
        "directors": movie.directors,
        "certification": movie.certification,
        "likes": likes,
        "dislikes": dislikes
    })


@router.post(
    "/",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_201_CREATED)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    existing_stmt = select(Movie).where(
        Movie.name == movie_data.name,
        Movie.year == movie_data.year,
        Movie.time == movie_data.time,
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()
    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=f"Movie with the name {movie_data.name} already exists."
        )

    try:
        certification_stmt = (select(Certification)
                              .where(Certification.name == movie_data.certification))
        certification_result = await db.execute(certification_stmt)
        certification = certification_result.scalars().first()
        if not certification:
            certification = Certification(name=movie_data.certification)
            db.add(certification)
            await db.flush()

        genres = []
        for genre_name in movie_data.genres:
            genre_stmt = select(Genre).where(Genre.name == genre_name)
            genre_result = await db.execute(genre_stmt)
            genre = genre_result.scalars().first()
            if not genre:
                genre = Genre(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        stars = []
        for star_name in movie_data.stars:
            star_stmt = select(Star).where(Star.name == star_name)
            star_result = await db.execute(star_stmt)
            star = star_result.scalars().first()
            if not star:
                star = Star(name=star_name)
                db.add(star)
                await db.flush()
            stars.append(star)

        directors = []
        for director_name in movie_data.directors:
            director_stmt = select(Director).where(Director.name == director_name)
            director_result = await db.execute(director_stmt)
            director = director_result.scalars().first()
            if not director:
                director = Director(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        movie = Movie(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification=certification,
            genres=genres,
            stars=stars,
            directors=directors
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, ["genres", "stars", "directors"])

        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db)
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    await db.delete(movie)
    await db.commit()

    return {"detail": "Movie deleted successfully."}


@router.patch("/{movie_id}", status_code=status.HTTP_200_OK)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db)
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}


@router.post(
    "/{movie_id}/like",
    response_model=MovieLikeResponseSchema,
    summary="Like or dislike a movie",
)
async def like_movie(
        movie_id: int,
        like_data: MovieLikeRequestSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
) -> MovieLikeResponseSchema:

    movie = (await db.execute(select(Movie).where(Movie.id == movie_id))).scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    existing_like_stmt = select(MovieLike).where(
        MovieLike.user_id == current_user.id,
        MovieLike.movie_id == movie_id
    )
    existing_like = (await db.execute(existing_like_stmt)).scalars().first()

    if existing_like:
        if existing_like.like_status == like_data.like_status:
            await db.delete(existing_like)
        else:
            existing_like.like_status = like_data.like_status
            db.add(existing_like)
    else:
        new_like = MovieLike(
            user_id=current_user.id,
            movie_id=movie_id,
            like_status=like_data.like_status
        )
        db.add(new_like)

    await db.commit()

    likes_count_stmt = select(func.count(MovieLike.user_id)).where(
        MovieLike.movie_id == movie_id,
        MovieLike.like_status == LikeStatusEnum.LIKE
    )
    dislikes_count_stmt = select(func.count(MovieLike.user_id)).where(
        MovieLike.movie_id == movie_id,
        MovieLike.like_status == LikeStatusEnum.DISLIKE
    )

    likes_count = (await db.execute(likes_count_stmt)).scalar_one()
    dislikes_count = (await db.execute(dislikes_count_stmt)).scalar_one()

    final_user_like = (await db.execute(existing_like_stmt)).scalars().first()

    return MovieLikeResponseSchema(
        likes=likes_count,
        dislikes=dislikes_count,
        user_status=final_user_like.like_status if final_user_like else None
    )

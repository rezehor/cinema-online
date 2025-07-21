from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from Cinema.database import get_db
from Cinema.models import Movie, Certification, Genre, Star, Director
from Cinema.schemas.movies import MovieListResponseSchema, MovieListItemSchema, MovieDetailSchema, MovieCreateSchema

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


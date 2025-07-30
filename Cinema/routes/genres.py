from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from Cinema.config.dependencies import require_moderator_or_admin
from Cinema.database import get_db
from Cinema.models import Genre, MovieGenres, User
from Cinema.schemas.movies import GenreListResponseSchema, GenreWithCountSchema, GenreSchema, GenreCreateSchema

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


@router.post(
    "/",
    response_model=GenreSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_genre(
        data: GenreCreateSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_moderator_or_admin)
) -> GenreSchema:
    existing_stmt = select(Genre).where(Genre.name == data.name)
    existing_result = await db.execute(existing_stmt)
    existing_genre = existing_result.scalars().first()

    if existing_genre:
        raise HTTPException(
            status_code=409,
            detail=f"Genre with the name {data.name} already exists."
        )

    try:
        new_genre = Genre(
            name=data.name,
        )
        db.add(new_genre)
        await db.commit()
        await db.refresh(new_genre)

        return GenreSchema(
            id=new_genre.id,
            name=new_genre.name,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

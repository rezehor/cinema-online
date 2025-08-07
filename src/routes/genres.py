from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from config.dependencies import require_moderator_or_admin
from database import get_db
from models import Genre, MovieGenres, User
from schemas.movies import (
    GenreListResponseSchema,
    GenreWithCountSchema,
    GenreSchema,
    GenreCreateUpdateSchema,
)

router = APIRouter()


@router.get(
    "/",
    response_model=GenreListResponseSchema,
    summary="List all genres with movie counts",
    description="Retrieves a list of all movie genres, each accompanied by a count of how many movies belong to that genre.",
)
async def get_genres_with_movie_count(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Genre.id,
            Genre.name,
            func.count(MovieGenres.c.movie_id).label("movie_count"),
        )
        .join(MovieGenres, MovieGenres.c.genre_id == Genre.id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    result = await db.execute(stmt)
    genres = result.all()

    genre_list = [
        GenreWithCountSchema(
            id=genre.id, name=genre.name, movie_count=genre.movie_count
        )
        for genre in genres
    ]

    return GenreListResponseSchema(genres=genre_list)


@router.post(
    "/",
    response_model=GenreSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new genre (Admin and moderator only)",
    description="Allows administrators and moderators to add a new genre to the database.",
)
async def create_genre(
    data: GenreCreateUpdateSchema,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_moderator_or_admin),
) -> GenreSchema:
    existing_stmt = select(Genre).where(Genre.name == data.name)
    existing_result = await db.execute(existing_stmt)
    existing_genre = existing_result.scalars().first()

    if existing_genre:
        raise HTTPException(
            status_code=409, detail=f"Genre with the name {data.name} already exists."
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


@router.put(
    "/{genre_id}",
    response_model=GenreSchema,
    status_code=status.HTTP_200_OK,
    summary="Update a genre's name (Admin and moderator only)",
    description="Allows administrators and moderators to update the name of an existing genre.",
)
async def update_genre(
    genre_id: int,
    data: GenreCreateUpdateSchema,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_moderator_or_admin),
) -> GenreSchema:
    stmt = select(Genre).where(Genre.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=404, detail="Genre with the given ID was not found."
        )

    genre.name = data.name
    try:
        await db.commit()
        await db.refresh(genre)
        return GenreSchema(id=genre.id, name=genre.name)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.delete(
    "/{genre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a genre (Admin and moderator only)",
    description="Allows administrators and moderators to permanently delete a genre from the database. This action may be restricted if the genre is associated with existing movies.",
)
async def delete_genre(
    genre_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_moderator_or_admin),
):
    stmt = select(Genre).where(Genre.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=404, detail="Genre with the given ID was not found."
        )

    await db.delete(genre)
    await db.commit()

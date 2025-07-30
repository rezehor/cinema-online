from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from Cinema.config.dependencies import require_moderator_or_admin
from Cinema.database import get_db
from Cinema.models import User, Star
from Cinema.schemas.movies import StarSchema, StarCreateUpdateSchema

router = APIRouter()


@router.get("/", response_model=List[StarSchema])
async def get_all_stars(db: AsyncSession = Depends(get_db)) -> List[StarSchema]:
    stmt = select(Star).order_by(Star.name)
    result = await db.execute(stmt)
    stars = result.scalars().all()

    return [StarSchema.model_validate(star) for star in stars]


@router.post(
    "/",
    response_model=StarSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_star(
        data: StarCreateUpdateSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_moderator_or_admin),
) -> StarSchema:
    existing_stmt = select(Star).where(Star.name == data.name)
    existing_result = await db.execute(existing_stmt)
    existing_star = existing_result.scalars().first()

    if existing_star:
        raise HTTPException(
            status_code=409,
            detail=f"Star with the name {data.name} already exists."
        )

    try:
        new_star = Star(
            name=data.name,
        )
        db.add(new_star)
        await db.commit()
        await db.refresh(new_star)
        return StarSchema.model_validate(new_star)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

@router.put(
    "/{star_id}",
    response_model=StarSchema,
    status_code=status.HTTP_200_OK,
    summary="Update a star",
)
async def update_star(
        star_id: int,
        data: StarCreateUpdateSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_moderator_or_admin),
) -> StarSchema:
    stmt = select(Star).where(Star.id == star_id)
    result = await db.execute(stmt)
    star = result.scalars().first()

    if not star:
        raise HTTPException(status_code=404, detail="Star with the given ID was not found.")

    star.name = data.name
    try:
        await db.commit()
        await db.refresh(star)
        return StarSchema.model_validate(star)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.delete(
    "/{star_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a star",
)
async def delete_star(
        star_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_moderator_or_admin),
):
    stmt = select(Star).where(Star.id == star_id)
    result = await db.execute(stmt)
    star = result.scalars().first()

    if not star:
        raise HTTPException(status_code=404, detail="Star with the given ID was not found.")

    await db.delete(star)
    await db.commit()

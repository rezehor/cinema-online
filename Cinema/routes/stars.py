from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from Cinema.config.dependencies import require_moderator_or_admin
from Cinema.database import get_db
from Cinema.models import User, Star
from Cinema.schemas.movies import StarSchema

router = APIRouter()


@router.get("/", response_model=List[StarSchema])
async def get_genres_with_movie_count(db: AsyncSession = Depends(get_db)) -> List[StarSchema]:
    stmt = select(Star).order_by(Star.name)
    result = await db.execute(stmt)
    stars = result.scalars().all()

    return [StarSchema.model_validate(star) for star in stars]
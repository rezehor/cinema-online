from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Cinema.config.dependencies import get_s3_storage_client, get_current_user
from Cinema.database import get_db
from Cinema.exceptions.storage import S3FileUploadError
from Cinema.models import User, UserProfile, GenderEnum
from Cinema.schemas.profiles import ProfileCreateSchema, ProfileResponseSchema, ProfileUpdateSchema
from Cinema.storages.interfaces import S3StorageInterface


router = APIRouter()

@router.post(
    "/",
    response_model=ProfileResponseSchema,
    summary="Create user profile",
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
        db: AsyncSession = Depends(get_db),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client),
        profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
        current_user: User = Depends(get_current_user)
) -> ProfileResponseSchema:

    stmt_profile = select(UserProfile).where(UserProfile.user_id == current_user.id)
    result_profile = await db.execute(stmt_profile)
    existing_profile = result_profile.scalars().first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a profile."
        )

    avatar_bytes = await profile_data.avatar.read()
    avatar_key = f"avatars/{current_user.id}_{profile_data.avatar.filename}"

    try:
        await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
    except S3FileUploadError as e:
        print(f"Error uploading avatar to S3: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfile(
        user_id=current_user.id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=cast(GenderEnum, profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    avatar_url = await s3_client.get_file_url(new_profile.avatar)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=cast(HttpUrl, avatar_url)
    )

@router.get(
    "/me/",
    response_model=ProfileResponseSchema,
    summary="Get current user's profile",
)
async def get_own_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
) -> ProfileResponseSchema:
    stmt = select(UserProfile).where(UserProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found."
        )

    avatar_url = None
    if profile.avatar:
        avatar_url = await s3_client.get_file_url(profile.avatar)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=cast(HttpUrl, avatar_url) if avatar_url else None
    )


@router.patch(
    "/",
    response_model=ProfileResponseSchema,
    summary="Update current user's profile",
)
async def update_profile(
    profile_data: ProfileUpdateSchema = Depends(ProfileUpdateSchema.as_form),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    current_user: User = Depends(get_current_user)
) -> ProfileResponseSchema:
    stmt = select(UserProfile).where(UserProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found."
        )

    if profile_data.first_name is not None:
        profile.first_name = profile_data.first_name
    if profile_data.last_name is not None:
        profile.last_name = profile_data.last_name
    if profile_data.gender is not None:
        profile.gender = profile_data.gender
    if profile_data.date_of_birth is not None:
        profile.date_of_birth = profile_data.date_of_birth
    if profile_data.info is not None:
        profile.info = profile_data.info

    if profile_data.avatar is not None:
        avatar_bytes = await profile_data.avatar.read()
        avatar_key = f"avatars/{current_user.id}_{profile_data.avatar.filename}"
        try:
            await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
            profile.avatar = avatar_key
        except S3FileUploadError as e:
            print(f"Error uploading avatar to S3: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later."
            )

    await db.commit()
    await db.refresh(profile)

    avatar_url = None
    if profile.avatar:
        avatar_url = await s3_client.get_file_url(profile.avatar)

    return ProfileResponseSchema(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=cast(HttpUrl, avatar_url) if avatar_url else None
    )

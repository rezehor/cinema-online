import uuid
from typing import cast, Tuple, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Cinema.config.dependencies import (
    get_s3_storage_client,
    get_current_user,
    profile_data_from_form,
    update_profile_data_from_form,
)
from Cinema.database import get_db
from Cinema.exceptions.storage import S3FileUploadError
from Cinema.models import User, UserProfile, GenderEnum, UserGroupEnum
from Cinema.schemas.profiles import (
    ProfileCreateSchema,
    ProfileResponseSchema,
    ProfileUpdateSchema,
)
from Cinema.storages.interfaces import S3StorageInterface


router = APIRouter()


@router.post(
    "/",
    response_model=ProfileResponseSchema,
    summary="Create own user profile",
    description="Allows an authenticated user to create their own profile. A user can only have one profile.",
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    form_data: Tuple[ProfileCreateSchema, Optional[UploadFile]] = Depends(
        profile_data_from_form
    ),
    current_user: User = Depends(get_current_user),
) -> ProfileResponseSchema:

    profile_data, avatar = form_data

    stmt_profile = select(UserProfile).where(UserProfile.user_id == current_user.id)
    result_profile = await db.execute(stmt_profile)
    existing_profile = result_profile.scalars().first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a profile.",
        )

    avatar_key = None
    if avatar:
        avatar_bytes = await avatar.read()
        avatar_key = f"avatars/{current_user.id}_{avatar.filename}"
        try:
            await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
        except S3FileUploadError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later.",
            )

    new_profile = UserProfile(
        user_id=current_user.id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=cast(GenderEnum, profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    avatar_url = None
    if new_profile.avatar:
        avatar_url = await s3_client.get_file_url(new_profile.avatar)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=cast(HttpUrl, avatar_url),
    )


@router.get(
    "/me/",
    response_model=ProfileResponseSchema,
    summary="Get current user's profile",
    description="Retrieves the profile data for the currently authenticated user."
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
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found."
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
        avatar=cast(HttpUrl, avatar_url) if avatar_url else None,
    )


@router.patch(
    "/",
    response_model=ProfileResponseSchema,
    summary="Update current user's profile",
    description="Allows an authenticated user to perform a partial update of their own profile. Only the provided fields will be changed."
)
async def update_profile(
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    form_data: Tuple[ProfileUpdateSchema, Optional[UploadFile]] = Depends(
        update_profile_data_from_form
    ),
    current_user: User = Depends(get_current_user),
) -> ProfileResponseSchema:
    profile_data, avatar = form_data

    stmt = select(UserProfile).where(UserProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

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

    if avatar:
        avatar_bytes = await avatar.read()
        if not avatar_bytes:
            raise HTTPException(
                status_code=400, detail="Uploaded avatar file is empty."
            )

        ext = avatar.filename.split(".")[-1]
        avatar_key = f"avatars/{current_user.id}_{uuid.uuid4().hex}.{ext}"

        try:
            await s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
            profile.avatar = avatar_key
        except S3FileUploadError:
            raise HTTPException(status_code=500, detail="Failed to upload avatar.")

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
        avatar=cast(HttpUrl, avatar_url) if avatar_url else None,
    )


@router.get(
    "/{user_id}",
    response_model=ProfileResponseSchema,
    summary="Get a specific user's profile (Admin/Moderator only)",
    description="Allows an administrator or moderator to retrieve the profile of any user by their ID.",
    status_code=status.HTTP_200_OK,
)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    current_user: User = Depends(get_current_user),
) -> ProfileResponseSchema:

    if current_user.group.name not in [
        UserGroupEnum.ADMIN.value,
        UserGroupEnum.MODERATOR.value,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view other users' profiles.",
        )

    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found."
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
        avatar=cast(HttpUrl, avatar_url) if avatar_url else None,
    )

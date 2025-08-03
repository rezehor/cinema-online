from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status

from Cinema.config.dependencies import (
    get_settings,
    get_jwt_auth_manager,
    get_accounts_email_notificator,
    get_current_user,
)
from Cinema.config.settings import Settings
from Cinema.database import get_db
from Cinema.exceptions.security import BaseSecurityError
from Cinema.models import (
    User,
    UserGroup,
    UserGroupEnum,
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
)
from Cinema.notifications.interfaces import EmailSenderInterface
from Cinema.schemas.users import (
    UserRegistrationResponseSchema,
    UserRegistrationRequestSchema,
    MessageResponseSchema,
    UserActivationRequestSchema,
    PasswordResetRequestSchema,
    PasswordResetCompleteRequestSchema,
    UserLoginResponseSchema,
    TokenRefreshResponseSchema,
    TokenRefreshRequestSchema,
    ResendActivationRequestSchema,
    ChangePasswordRequestSchema,
)
from Cinema.security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new, inactive user account. An activation email will be sent to the provided email address."
)
async def register_user(
    user_data: UserRegistrationRequestSchema,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> UserRegistrationResponseSchema:
    existing_stmt = select(User).where(User.email == user_data.email)
    existing_result = await db.execute(existing_stmt)
    existing_user = existing_result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists.",
        )

    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db.execute(stmt)
    user_group = result.scalars().first()

    if not user_group:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default user group not found.",
        )

    try:
        new_user = User.create(
            email=str(user_data.email),
            raw_password=user_data.password,
            group_id=user_group.id,
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationToken(user_id=new_user.id)
        db.add(activation_token)

        await db.commit()
        await db.refresh(new_user)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation.",
        ) from e
    else:
        activation_link = "http://127.0.0.1:8000/api/v1/users/activate/"

        await email_sender.send_activation_email(new_user.email, activation_link)

        return UserRegistrationResponseSchema.model_validate(new_user)


@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Activate user account",
    description="Activate a user's account using the token "
                "sent to their email. The token is valid for 24 hours."
)
async def activate_user(
    activation_data: UserActivationRequestSchema,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    stmt = (
        select(ActivationToken)
        .options(joinedload(ActivationToken.user))
        .join(User)
        .where(
            User.email == activation_data.email,
            ActivationToken.token == activation_data.token,
        )
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)

    if (
        not token_record
        or cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc)
        < now_utc
    ):
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token.",
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active.",
        )

    user.is_active = True
    await db.delete(token_record)
    await db.commit()

    login_link = "http://127.0.0.1:8000/api/v1/users/login/"

    await email_sender.send_activation_complete_email(
        str(activation_data.email), login_link
    )

    return MessageResponseSchema(message="User account activated successfully.")


@router.post(
    "/resend-activation-token",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Resend activation token",
    description="If the original activation token has expired, "
                "a user can request a new one. A new link, "
                "valid for 24 hours, will be sent to their email."
)
async def resend_activation_token(
    request_data: ResendActivationRequestSchema,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    stmt = select(User).where(User.email == request_data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or user.is_active:
        return MessageResponseSchema(
            message="If you are registered, you will receive an email with instructions."
        )

    await db.execute(delete(ActivationToken).where(ActivationToken.user_id == user.id))

    new_token = ActivationToken(user_id=user.id)
    db.add(new_token)
    await db.commit()
    await db.refresh(new_token)

    activation_link = "http://127.0.0.1:8000/api/v1/users/activate/"

    await email_sender.send_activation_email(user.email, activation_link)

    return MessageResponseSchema(
        message="If you are registered, you will receive an email with instructions."
    )


@router.post(
    "/password-reset/request/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Request a password reset",
    description="Initiates the password reset process. An email with a reset link will be sent to the user if their account exists.",
)
async def request_password_reset_token(
    request_data: PasswordResetRequestSchema,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    stmt = select(User).filter_by(email=request_data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        return MessageResponseSchema(
            message="If you are registered, you will receive an email with instructions."
        )

    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )

    reset_token = PasswordResetToken(user_id=cast(int, user.id))
    db.add(reset_token)
    await db.commit()

    password_reset_complete_link = (
        "http://127.0.0.1:8000/api/v1/users/password-reset-complete/"
    )

    await email_sender.send_password_reset_email(
        str(request_data.email), password_reset_complete_link
    )

    return MessageResponseSchema(
        message="If you are registered, you will receive an email with instructions."
    )


@router.post(
    "/password-reset/complete/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Complete password reset",
    description="Set a new password using the token sent to the user's email."
)
async def password_reset_complete(
    data: PasswordResetCompleteRequestSchema,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    stmt = select(User).filter_by(email=data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token."
        )

    stmt = select(PasswordResetToken).filter_by(user_id=user.id)
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    if not token_record or token_record.token != data.token:
        if token_record:
            await db.run_sync(lambda s: s.delete(token_record))
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token."
        )

    expires_at = cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.run_sync(lambda s: s.delete(token_record))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token."
        )

    try:
        user.password = data.password
        await db.run_sync(lambda s: s.delete(token_record))
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password.",
        )

    login_link = "http://127.0.0.1:8000/api/v1/users/login/"

    await email_sender.send_password_reset_complete_email(str(data.email), login_link)

    return MessageResponseSchema(message="Password reset successfully.")


@router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="User login",
    description="Authenticate a user with their email and password. Returns JWT access and refresh tokens upon success.",
)
async def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserLoginResponseSchema:
    stmt = select(User).filter_by(email=username)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.verify_password(password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.flush()

    jwt_refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    try:
        refresh_token = RefreshToken.create(
            user_id=user.id,
            days_valid=settings.LOGIN_TIME_DAYS,
            token=jwt_refresh_token,
        )
        db.add(refresh_token)
        await db.flush()
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )

    jwt_access_token = jwt_manager.create_access_token({"user_id": user.id})
    return UserLoginResponseSchema(
        access_token=jwt_access_token,
        refresh_token=jwt_refresh_token,
    )


@router.post(
    "/logout/",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponseSchema,
    summary="User logout",
    description="Logs a user out by invalidating their refresh token. The client is responsible for deleting the tokens from storage."
)
async def logout_user(
    data: TokenRefreshRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    await db.execute(
        delete(RefreshToken).where(RefreshToken.token == data.refresh_token)
    )
    await db.commit()

    return MessageResponseSchema(message="Successfully logged out.")


@router.post(
    "/refresh/",
    response_model=TokenRefreshResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Use a valid refresh token to obtain a new access token."
)
async def refresh_access_token(
    token_data: TokenRefreshRequestSchema,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> TokenRefreshResponseSchema:
    try:
        decoded_token = jwt_manager.decode_refresh_token(token_data.refresh_token)
        user_id = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    stmt = select(RefreshToken).filter_by(token=token_data.refresh_token)
    result = await db.execute(stmt)
    refresh_token_record = result.scalars().first()
    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    stmt = select(User).filter_by(id=user_id)
    result = await db.execute(stmt)

    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    new_access_token = jwt_manager.create_access_token({"user_id": user_id})

    return TokenRefreshResponseSchema(access_token=new_access_token)


@router.delete(
    "/{user_id}",
    summary="Delete a user (Admin only)",
    description="Allows an administrator to delete a user account. This action is irreversible.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if current_user.group.name != UserGroupEnum.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete users",
        )
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=404, detail="User with the given ID was not found."
        )

    await db.delete(user)
    await db.commit()


@router.post(
    "/change-password/",
    response_model=MessageResponseSchema,
    summary="Change current user's password",
    description="Allows an authenticated user to change their own password by providing the old password and a new one. This action invalidates all other active sessions."
)
async def change_password(
    request_data: ChangePasswordRequestSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponseSchema:

    if not current_user.verify_password(request_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password."
        )

    if request_data.password == request_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the old password.",
        )

    current_user.password = request_data.new_password
    db.add(current_user)

    await db.execute(
        delete(RefreshToken).where(RefreshToken.user_id == current_user.id)
    )
    await db.commit()

    return MessageResponseSchema(message="Password has been changed successfully.")

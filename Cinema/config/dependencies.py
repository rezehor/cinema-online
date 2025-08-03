from datetime import datetime
from typing import Optional, Tuple, Union
from fastapi import Depends, HTTPException, status, Form, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from Cinema.config.settings import Settings, BaseAppSettings
from Cinema.database import get_db
from Cinema.models import User
from Cinema.notifications.emails import EmailSender
from Cinema.notifications.interfaces import EmailSenderInterface
from Cinema.schemas.profiles import ProfileCreateSchema, ProfileUpdateSchema
from Cinema.security.interfaces import JWTAuthManagerInterface
from Cinema.security.token_manager import JWTAuthManager
from Cinema.storages.interfaces import S3StorageInterface
from Cinema.storages.s3 import S3StorageClient


def get_settings() -> Settings:
    return Settings()


def get_jwt_auth_manager(
    settings: Settings = Depends(get_settings),
) -> JWTAuthManagerInterface:
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM,
    )

def get_accounts_email_notificator(
    settings: BaseAppSettings = Depends(get_settings)
) -> EmailSenderInterface:

    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        email=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        template_dir=settings.PATH_TO_EMAIL_TEMPLATES_DIR,
        activation_email_template_name=settings.ACTIVATION_EMAIL_TEMPLATE_NAME,
        activation_complete_email_template_name=settings.ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME,
        password_email_template_name=settings.PASSWORD_RESET_TEMPLATE_NAME,
        password_complete_email_template_name=settings.PASSWORD_RESET_COMPLETE_TEMPLATE_NAME,
        order_confirmation_email_template_name=settings.ORDER_CONFIRMATION_EMAIL_TEMPLATE_NAME
    )

def get_s3_storage_client(
    settings: BaseAppSettings = Depends(get_settings)
) -> S3StorageInterface:

    return S3StorageClient(
        endpoint_url=settings.S3_STORAGE_ENDPOINT,
        access_key=settings.S3_STORAGE_ACCESS_KEY,
        secret_key=settings.S3_STORAGE_SECRET_KEY,
        bucket_name=settings.S3_BUCKET_NAME
    )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login/")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt_manager.decode_access_token(token)
        user_id: Optional[int] = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = (select(User).options(
        joinedload(User.group),
            joinedload(User.favorite_movies))
            .filter_by(id=user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )

    return user


def require_moderator_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.group.name not in {"admin", "moderator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    return current_user


def profile_data_from_form(
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: Optional[str] = Form(None),
    date_of_birth: Optional[str] = Form(None),
    info: Optional[str] = Form(None),
    avatar: Union[UploadFile, str, None] = File(None)
) -> Tuple[ProfileCreateSchema, Optional[UploadFile]]:

    gender = gender.strip() if gender and gender.strip() else None
    info = info.strip() if info and info.strip() else None

    dob_value = None
    if date_of_birth:
        try:
            dob_value = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid date format for date_of_birth. Use YYYY-MM-DD"
            )

    if isinstance(avatar, str) and avatar.strip() == "":
        avatar = None

    profile = ProfileCreateSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=dob_value,
        info=info
    )

    if avatar and hasattr(avatar, "filename"):
        return profile, avatar

    return profile, None

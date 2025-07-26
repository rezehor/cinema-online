from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR: Path = Path(__file__).parent.parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        extra="ignore"
    )

    PATH_TO_EMAIL_TEMPLATES_DIR: str = str(BASE_DIR / "Cinema" / "notifications" / "templates")
    ACTIVATION_EMAIL_TEMPLATE_NAME: str = "activation_request.html"
    ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME: str = "activation_complete.html"
    PASSWORD_RESET_TEMPLATE_NAME: str = "password_reset_request.html"
    PASSWORD_RESET_COMPLETE_TEMPLATE_NAME: str = "password_reset_complete.html"

    LOGIN_TIME_DAYS: int = 7

    EMAIL_HOST: str = "localhost"
    EMAIL_PORT: int = 25
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    EMAIL_USE_TLS: bool = False
    MAILHOG_API_PORT: int = 8025

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    S3_STORAGE_HOST: str = "localhost"
    S3_STORAGE_PORT: int = 9000
    S3_STORAGE_ACCESS_KEY: str = "minioadmin"
    S3_STORAGE_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "theater-storage"

    @property
    def S3_STORAGE_ENDPOINT(self) -> str:
        return f"http://{self.S3_STORAGE_HOST}:{self.S3_STORAGE_PORT}"


class Settings(BaseAppSettings):

    SECRET_KEY_ACCESS: str
    SECRET_KEY_REFRESH: str
    JWT_SIGNING_ALGORITHM: str

settings = Settings()

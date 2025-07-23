import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOGIN_TIME_DAYS: int = 7
    SECRET_KEY_ACCESS: str = os.getenv("SECRET_KEY_ACCESS")
    SECRET_KEY_REFRESH: str = os.getenv("SECRET_KEY_REFRESH")
    JWT_SIGNING_ALGORITHM: str = os.getenv("JWT_SIGNING_ALGORITHM")

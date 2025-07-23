from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOGIN_TIME_DAYS: int = 7
    SECRET_KEY_ACCESS: str
    SECRET_KEY_REFRESH: str
    JWT_SIGNING_ALGORITHM: str

    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")

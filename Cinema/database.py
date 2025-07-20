import pathlib
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SQLALCHEMY_DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'online_cinema.db'}"



engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker( # type: ignore
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

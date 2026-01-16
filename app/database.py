from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from collections.abc import AsyncGenerator

DB_URL = "postgresql+asyncpg://Fadmin:1121qwe@localhost:5432/redmic_db"

a_engine = create_async_engine(DB_URL, echo=True)  # echo в проде убрать

async_session_maker = async_sessionmaker(
    a_engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
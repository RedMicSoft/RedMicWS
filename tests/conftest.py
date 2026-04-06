import asyncio
from typing import AsyncGenerator, Dict, Generator
import uuid as uuid_module
from datetime import date
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# media/ и team_files/ создаются при импорте app-модулей, но на всякий случай:
Path("media").mkdir(exist_ok=True)
Path("team_files").mkdir(exist_ok=True)

from app.database import Base, get_db
from app.main import app
from app.levels.models import Level, UserLevel
from app.users.models import User
from app.users.utils import hash_password

TEST_DB_URL = "sqlite+aiosqlite:///./test_redmic.db"

_engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
TestSession = async_sessionmaker(_engine, expire_on_commit=False)


async def _get_test_db():
    async with TestSession() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    """Создаёт таблицы перед всеми тестами, удаляет после."""

    async def _create():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await _engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_drop())
    Path("./test_redmic.db").unlink(missing_ok=True)


@pytest_asyncio.fixture
@pytest.mark.usefixtures("setup_database")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTPX-клиент с переопределённым get_db на тестовую SQLite."""
    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(
    request: pytest.FixtureRequest, client: AsyncClient
) -> Dict[str, str]:
    """
    Создаёт пользователя (access_level=request.param["level"]) напрямую в БД,
    логинится через API и возвращает заголовок Authorization.
    Никнейм уникален, чтобы тесты не конфликтовали между собой.
    """
    if not hasattr(request, "param") or "level" not in request.param:
        raise ValueError("Параметр 'level' обязателен для фикстуры auth_headers")

    print(
        f"Создаём тестового пользователя с уровнем доступа {request.param['level']}..."
    )

    nickname = f"test_{uuid_module.uuid4().hex[:8]}"

    async with TestSession() as session:
        level = Level(
            role_name="пользователь",
            access_level=request.param["level"],
            is_active=True,
        )
        session.add(level)
        await session.flush()

        user = User(
            nickname=nickname,
            hashed_password=hash_password("test_pass"),
            join_date=date.today(),
        )
        session.add(user)
        await session.flush()

        session.add(UserLevel(level_id=level.level_id, user_id=user.user_id))
        await session.commit()

        user_id = user.user_id
        level_id = level.level_id

    async def _cleanup() -> None:
        async with TestSession() as session:
            db_user = await session.get(User, user_id)
            if db_user:
                await session.delete(db_user)
            await session.commit()
            db_level = await session.get(Level, level_id)
            if db_level:
                await session.delete(db_level)
            await session.commit()

    request.addfinalizer(lambda: asyncio.run(_cleanup()))

    response = await client.post(
        "/users/login",
        data={"username": nickname, "password": "test_pass"},
    )
    assert response.status_code == 200, f"Логин не удался: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

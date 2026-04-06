from datetime import date

from httpx import AsyncClient

from tests.conftest import TestSession
from tests.helpers import _uid
from app.levels.models import Level, UserLevel
from app.users.models import User
from app.users.utils import hash_password


async def create_user() -> User:
    async with TestSession() as s:
        user = User(
            nickname=f"worker_{_uid()}",
            hashed_password=hash_password("x"),
            join_date=date.today(),
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


async def create_user_with_level(access_level: int) -> tuple[User, Level]:
    async with TestSession() as s:
        level = Level(role_name=f"role_{_uid()}", access_level=access_level, is_active=True)
        s.add(level)
        await s.flush()
        user = User(
            nickname=f"u_{_uid()}",
            hashed_password=hash_password("x"),
            join_date=date.today(),
        )
        s.add(user)
        await s.flush()
        s.add(UserLevel(level_id=level.level_id, user_id=user.user_id))
        await s.commit()
        await s.refresh(user)
        await s.refresh(level)
        return user, level


async def login_user(client: AsyncClient, nickname: str, password: str = "x") -> dict:
    response = await client.post("/users/login", data={"username": nickname, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

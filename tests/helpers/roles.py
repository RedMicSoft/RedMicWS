import asyncio

import pytest

from tests.conftest import TestSession
from tests.helpers import _uid
from app.roles.models import Role


async def create_role(
    series_id: int,
    user_id: int,
    request: pytest.FixtureRequest | None = None,
    **kwargs,
) -> Role:
    defaults = dict(
        role_name=f"role_{_uid()}",
        user_id=user_id,
        series_id=series_id,
        srt_url="",
    )
    defaults.update(kwargs)
    async with TestSession() as s:
        role = Role(**defaults)
        s.add(role)
        await s.commit()
        await s.refresh(role)

    if request is not None:
        role_id = role.role_id

        async def _delete() -> None:
            async with TestSession() as s:
                db_role = await s.get(Role, role_id)
                if db_role:
                    await s.delete(db_role)
                await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return role

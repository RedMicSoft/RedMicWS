from tests.conftest import TestSession
from tests.helpers import _uid
from app.roles.models import Role


async def create_role(series_id: int, user_id: int, **kwargs) -> Role:
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
        return role

from datetime import date

from tests.conftest import TestSession
from tests.helpers import _uid
from app.projects.models import Project


async def create_project(curator_id: int) -> Project:
    async with TestSession() as s:
        project = Project(
            title=f"proj_{_uid()}",
            type="dub",
            curator_id=curator_id,
            created_at=date.today(),
            status="active",
        )
        s.add(project)
        await s.commit()
        await s.refresh(project)
        return project

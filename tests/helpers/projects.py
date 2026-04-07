import asyncio
from datetime import date

import pytest

from tests.conftest import TestSession
from tests.helpers import _uid
from app.projects.models import Project


async def create_project(
    curator_id: int,
    request: pytest.FixtureRequest | None = None,
) -> Project:
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

    if request is not None:
        project_id = project.project_id

        async def _delete() -> None:
            async with TestSession() as s:
                db_project = await s.get(Project, project_id)
                if db_project:
                    await s.delete(db_project)
                await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return project

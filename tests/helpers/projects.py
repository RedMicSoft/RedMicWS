import asyncio
from datetime import date

import pytest

from tests.conftest import TestSession
from tests.helpers import _uid
from app.projects.models import Project, ProjectRoleHistory


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


async def create_project_role(
    project_id: int,
    user_id: int,
    role_title: str | None = None,
    image_url: str = "",
    request: pytest.FixtureRequest | None = None,
) -> ProjectRoleHistory:
    if role_title is None:
        role_title = f"role_{_uid()}"
    async with TestSession() as s:
        role = ProjectRoleHistory(
            project_id=project_id,
            role_title=role_title,
            user_id=user_id,
            image_url=image_url,
        )
        s.add(role)
        await s.commit()
        await s.refresh(role)

    if request is not None:
        role_id = role.role_id

        async def _delete() -> None:
            async with TestSession() as s:
                db_role = await s.get(ProjectRoleHistory, role_id)
                if db_role:
                    await s.delete(db_role)
                await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return role

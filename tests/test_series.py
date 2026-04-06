import asyncio
import pytest
from httpx import AsyncClient

from tests.conftest import TestSession
from tests.helpers.users import create_user, create_user_with_level, login_user
from tests.helpers.projects import create_project
from tests.helpers.series import create_series, STAFF_WORK_TYPES
from tests.helpers.roles import create_role
from app.levels.models import Level
from app.users.models import User
from app.projects.models import Project
from app.roles.models import RoleState


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_work_existing_series_endpoint(auth_headers: dict, client: AsyncClient):
    response = await client.get("/series/", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "В данном проекте ещё нет серий."}


# ---------------------------------------------------------------------------
# Scenario 1: одна серия, пользователь занимает все 6 должностей + 2 роли актёра
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_work_all_positions_and_roles(auth_headers: dict, client: AsyncClient):
    worker = await create_user()
    project = await create_project(curator_id=worker.user_id)
    series = await create_series(
        project.project_id,
        curator=worker.user_id,
        sound_engineer=worker.user_id,
        raw_sound_engineer=worker.user_id,
        timer=worker.user_id,
        translator=worker.user_id,
        director=worker.user_id,
    )
    await create_role(series.id, worker.user_id)
    await create_role(series.id, worker.user_id)

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 8  # 6 должностей + 2 роли

    work_types = [item["work_type"] for item in data]
    assert set(work_types) == STAFF_WORK_TYPES | {"актёр"}
    assert work_types.count("актёр") == 2

    for item in data:
        assert item["seria"]["seria_id"] == series.id
        assert item["seria"]["seria_title"] == series.title
        assert item["project"]["project_id"] == project.project_id
        if item["work_type"] == "актёр":
            assert item["role"] is not None
            assert "role_name" in item["role"]
            assert "state" in item["role"]
        else:
            assert item["role"] is None


# ---------------------------------------------------------------------------
# Scenario 2: два проекта — в одном актёр, в другом куратор
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_work_across_two_projects(auth_headers: dict, client: AsyncClient):
    worker = await create_user()
    other = await create_user()

    project1 = await create_project(curator_id=other.user_id)
    series1 = await create_series(project1.project_id)
    await create_role(series1.id, worker.user_id)

    project2 = await create_project(curator_id=other.user_id)
    series2 = await create_series(project2.project_id, curator=worker.user_id)

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    project_ids = {item["project"]["project_id"] for item in data}
    assert project_ids == {project1.project_id, project2.project_id}

    actor_item = next(i for i in data if i["work_type"] == "актёр")
    assert actor_item["project"]["project_id"] == project1.project_id
    assert actor_item["role"] is not None

    staff_item = next(i for i in data if i["work_type"] == "куратор")
    assert staff_item["project"]["project_id"] == project2.project_id
    assert staff_item["role"] is None


# ---------------------------------------------------------------------------
# Scenario 3: у пользователя нет никакой работы
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_work_empty_when_no_assignments(auth_headers: dict, client: AsyncClient):
    worker = await create_user()

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Scenario 4: запрос без авторизации → 401
# ---------------------------------------------------------------------------


async def test_work_requires_auth(client: AsyncClient):
    response = await client.get("/series/user/1/work")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Дополнительные тесты
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_work_role_is_ready_flag(auth_headers: dict, client: AsyncClient):
    """role_is_ready=True только у роли в состоянии MIXING_READY."""
    worker = await create_user()
    other = await create_user()
    project = await create_project(curator_id=other.user_id)
    series = await create_series(project.project_id)

    await create_role(series.id, worker.user_id, state=RoleState.MIXING_READY)
    await create_role(series.id, worker.user_id, state=RoleState.NOT_LOADED)

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    ready = [i for i in data if i["role_is_ready"]]
    not_ready = [i for i in data if not i["role_is_ready"]]
    assert len(ready) == 1
    assert len(not_ready) == 1
    assert ready[0]["role"]["state"] == RoleState.MIXING_READY.value


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_work_subs_flag(auth_headers: dict, client: AsyncClient):
    """subs=True если у серии задан ass_url, иначе False."""
    worker = await create_user()
    other = await create_user()
    project = await create_project(curator_id=other.user_id)

    series_with_ass = await create_series(
        project.project_id,
        curator=worker.user_id,
        ass_url="/media/subs/test.ass",
    )
    series_without_ass = await create_series(
        project.project_id,
        sound_engineer=worker.user_id,
        ass_url=None,
    )

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    by_seria = {item["seria"]["seria_id"]: item for item in data}
    assert by_seria[series_with_ass.id]["subs"] is True
    assert by_seria[series_without_ass.id]["subs"] is False


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_work_staff_role_is_ready_is_false(auth_headers: dict, client: AsyncClient):
    """Для всех должностей (не актёр) role_is_ready всегда False."""
    worker = await create_user()
    project = await create_project(curator_id=worker.user_id)
    await create_series(
        project.project_id,
        curator=worker.user_id,
        sound_engineer=worker.user_id,
    )

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == 200
    for item in response.json():
        assert item["role_is_ready"] is False


# ---------------------------------------------------------------------------
# DELETE /series/{seria_id}
# ---------------------------------------------------------------------------


async def test_delete_series_no_auth(client: AsyncClient):
    response = await client.delete("/series/999999")
    assert response.status_code == 401


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_delete_series_not_found(auth_headers: dict, client: AsyncClient):
    response = await client.delete("/series/999999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_delete_series_forbidden_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    other = await create_user()
    project = await create_project(curator_id=other.user_id)
    series = await create_series(project.project_id)

    async def _cleanup():
        async with TestSession() as s:
            db_project = await s.get(Project, project.project_id)
            if db_project:
                await s.delete(db_project)
            db_user = await s.get(User, other.user_id)
            if db_user:
                await s.delete(db_user)
            await s.commit()

    request.addfinalizer(lambda: asyncio.run(_cleanup()))

    response = await client.delete(f"/series/{series.id}", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.parametrize("auth_headers", [{"level": 2}], indirect=True)
async def test_delete_series_ok_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    other = await create_user()
    project = await create_project(curator_id=other.user_id)
    series = await create_series(project.project_id)

    async def _cleanup():
        async with TestSession() as s:
            db_project = await s.get(Project, project.project_id)
            if db_project:
                await s.delete(db_project)
            db_user = await s.get(User, other.user_id)
            if db_user:
                await s.delete(db_user)
            await s.commit()

    request.addfinalizer(lambda: asyncio.run(_cleanup()))

    response = await client.delete(f"/series/{series.id}", headers=auth_headers)
    assert response.status_code == 204


async def test_delete_series_ok_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    curator, level = await create_user_with_level(access_level=1)
    project = await create_project(curator_id=curator.user_id)
    series = await create_series(project.project_id)
    headers = await login_user(client, curator.nickname)

    async def _cleanup():
        async with TestSession() as s:
            db_project = await s.get(Project, project.project_id)
            if db_project:
                await s.delete(db_project)
            db_user = await s.get(User, curator.user_id)
            if db_user:
                await s.delete(db_user)
            db_level = await s.get(Level, level.level_id)
            if db_level:
                await s.delete(db_level)
            await s.commit()

    request.addfinalizer(lambda: asyncio.run(_cleanup()))

    response = await client.delete(f"/series/{series.id}", headers=headers)
    assert response.status_code == 204

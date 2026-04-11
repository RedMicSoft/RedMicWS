"""
Tests for series role endpoints:
  POST   /series/{seria_id}/role
  DELETE /series/role/{role_id}
"""

import asyncio

import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy import select

from app.projects.models import ProjectRoleHistory
from tests.conftest import TestSession
from tests.helpers.users import create_user, create_user_with_level, login_user
from tests.helpers.projects import create_project, create_project_role
from tests.helpers.series import create_series
from tests.helpers.roles import create_role, post_role, put_role_actor
from app.roles.models import Role
from app.users.utils import MEMBER_LEVEL, CURATOR_LEVEL


# ===========================================================================
# POST /series/{seria_id}/role
# ===========================================================================


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_create_role_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await client.post("/series/9999/role", json={"role_name": "Test"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_role_series_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая серия → 404."""
    response = await post_role(client, 9999999, "SomeRole", auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 403
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_create_role_forbidden_for_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с серией/проектом → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await post_role(client, series.id, "TestRole", auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 201 — access by level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_role_success_by_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня >= 2 может создавать роль."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await post_role(client, series.id, "NewRole", auth_headers, request)
    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    assert body["role_name"] == "NewRole"
    assert body["actor"] is None
    assert body["fixes"] is None
    assert body["note"] == ""
    assert body["checked"] is False
    assert body["timed"] is False
    assert body["state"] == "не загружена"
    assert body["subtitle"] is None
    assert body["records"] is None

    async with TestSession() as s:
        db_role = await s.get(Role, body["id"])
        assert db_role is not None
        assert db_role.user_id is None


# ---------------------------------------------------------------------------
# 201 — access by project curator
# ---------------------------------------------------------------------------


async def test_create_role_success_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) может создавать роль."""
    curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    headers = await login_user(client, curator.nickname)

    response = await post_role(client, series.id, "ProjectCuratorRole", headers, request)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["role_name"] == "ProjectCuratorRole"


# ---------------------------------------------------------------------------
# 201 — access by series curator
# ---------------------------------------------------------------------------


async def test_create_role_success_by_series_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор серии (уровень 1) может создавать роль."""
    series_curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, curator=series_curator.user_id)
    headers = await login_user(client, series_curator.nickname)

    response = await post_role(client, series.id, "SeriesCuratorRole", headers, request)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["role_name"] == "SeriesCuratorRole"


# ---------------------------------------------------------------------------
# Duplicate name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_role_duplicate_name(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Дубликат названия (тот же регистр) → 400."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response1 = await post_role(client, series.id, "DuplicateRole", auth_headers, request)
    assert response1.status_code == status.HTTP_201_CREATED

    response2 = await post_role(client, series.id, "DuplicateRole", auth_headers)
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "уже создана" in response2.json()["detail"]


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_role_duplicate_name_case_insensitive(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Дубликат названия (другой регистр) → 400."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response1 = await post_role(client, series.id, "UniqueRole", auth_headers, request)
    assert response1.status_code == status.HTTP_201_CREATED

    response2 = await post_role(client, series.id, "uniquerole", auth_headers)
    assert response2.status_code == status.HTTP_400_BAD_REQUEST

    response3 = await post_role(client, series.id, "UNIQUEROLE", auth_headers)
    assert response3.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Actor assignment from project roles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_role_actor_from_project_roles(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Если роль с таким именем есть в project.roles, назначить актёра."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    await create_project_role(
        project_id=project.project_id,
        user_id=actor.user_id,
        role_title="Алекс",
        request=request,
    )

    response = await post_role(client, series.id, "Алекс", auth_headers, request)
    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    assert body["actor"] is not None
    assert body["actor"]["id"] == actor.user_id
    assert body["actor"]["nickname"] == actor.nickname


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_role_actor_from_project_roles_case_insensitive(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Поиск актёра в project.roles — регистронезависимый."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    await create_project_role(
        project_id=project.project_id,
        user_id=actor.user_id,
        role_title="BOSS",
        request=request,
    )

    response = await post_role(client, series.id, "boss", auth_headers, request)
    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    assert body["actor"] is not None
    assert body["actor"]["id"] == actor.user_id


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_role_no_project_role_match(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Если совпадения нет — actor должен быть null."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    await create_project_role(
        project_id=project.project_id,
        user_id=actor.user_id,
        role_title="OtherRole",
        request=request,
    )

    response = await post_role(client, series.id, "DifferentRole", auth_headers, request)
    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    assert body["actor"] is None

    async with TestSession() as s:
        db_role = await s.get(Role, body["id"])
        assert db_role is not None
        assert db_role.user_id is None


# ===========================================================================
# DELETE /series/role/{role_id}
# ===========================================================================


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_delete_role_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await client.delete("/series/role/9999999")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_role_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая роль → 404."""
    response = await client.delete("/series/role/9999999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 403
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_delete_role_forbidden_for_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без привязки к серии/проекту → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await client.delete(f"/series/role/{role.role_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 200 — access by level >= CURATOR_LEVEL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_role_success_by_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня >= 2 может удалить роль."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    # не регистрируем cleanup — роль будет удалена запросом
    role = await create_role(series.id, None)

    response = await client.delete(f"/series/role/{role.role_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "Роль успешно удалена из серии"

    async with TestSession() as s:
        assert await s.get(Role, role.role_id) is None


# ---------------------------------------------------------------------------
# 200 — access by project curator
# ---------------------------------------------------------------------------


async def test_delete_role_success_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) может удалить роль."""
    curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None)
    headers = await login_user(client, curator.nickname)

    response = await client.delete(f"/series/role/{role.role_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "Роль успешно удалена из серии"

    async with TestSession() as s:
        assert await s.get(Role, role.role_id) is None


# ---------------------------------------------------------------------------
# 200 — access by series curator
# ---------------------------------------------------------------------------


async def test_delete_role_success_by_series_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор серии (уровень 1) может удалить роль."""
    series_curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project_curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=project_curator.user_id, request=request)
    series = await create_series(project.project_id, request, curator=series_curator.user_id)
    role = await create_role(series.id, None)
    headers = await login_user(client, series_curator.nickname)

    response = await client.delete(f"/series/role/{role.role_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "Роль успешно удалена из серии"

    async with TestSession() as s:
        assert await s.get(Role, role.role_id) is None


# ===========================================================================
# PUT /series/role/{role_id}/actor
# ===========================================================================

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_set_role_actor_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await client.put("/series/role/9999/actor", json={"actor_id": 1})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_actor_role_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая роль → 404."""
    response = await put_role_actor(client, 9999999, 1, auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_actor_user_not_found(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Несуществующий актёр → 404."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await put_role_actor(
        client, role.role_id, 9999999, auth_headers, request
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 403 — forbidden
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_set_role_actor_forbidden_for_plain_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с серией/проектом → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    actor = await create_user(request)

    response = await put_role_actor(
        client, role.role_id, actor.user_id, auth_headers, request
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_set_role_actor_ok_for_series_curator(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор серии (уровень 1) имеет доступ."""
    series_curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project_owner, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=project_owner.user_id, request=request)
    series = await create_series(
        project.project_id, request, curator=series_curator.user_id
    )
    role = await create_role(series.id, None, request)
    actor = await create_user(request)
    headers = await login_user(client, series_curator.nickname)

    response = await put_role_actor(
        client, role.role_id, actor.user_id, headers, request
    )
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 200 — success
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_actor_success_by_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня >= 2 может установить актёра."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    actor = await create_user(request)

    response = await put_role_actor(
        client, role.role_id, actor.user_id, auth_headers, request
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["user_id"] == actor.user_id
    assert body["nickname"] == actor.nickname


async def test_set_role_actor_success_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) может установить актёра."""
    project_curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=project_curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    actor = await create_user(request)
    headers = await login_user(client, project_curator.nickname)

    response = await put_role_actor(
        client, role.role_id, actor.user_id, headers, request
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["user_id"] == actor.user_id
    assert body["nickname"] == actor.nickname


async def test_set_role_actor_success_by_series_director(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Режиссёр серии (уровень 1) может установить актёра."""
    director, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project_owner, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=project_owner.user_id, request=request)
    series = await create_series(project.project_id, request, director=director.user_id)
    role = await create_role(series.id, None, request)
    actor = await create_user(request)
    headers = await login_user(client, director.nickname)

    response = await put_role_actor(
        client, role.role_id, actor.user_id, headers, request
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["user_id"] == actor.user_id
    assert body["nickname"] == actor.nickname


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_actor_response_shape(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Ответ содержит user_id, nickname, avatar_url."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    actor = await create_user(request)

    response = await put_role_actor(
        client, role.role_id, actor.user_id, auth_headers, request
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert set(body.keys()) == {"user_id", "nickname", "avatar_url"}


# ---------------------------------------------------------------------------
# ProjectRoleHistory tracking
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_actor_creates_project_role_history(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Если роль отсутствует в ProjectRoleHistory — запись создаётся."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    actor = await create_user(request)

    response = await put_role_actor(
        client, role.role_id, actor.user_id, auth_headers, request
    )
    assert response.status_code == status.HTTP_200_OK

    async with TestSession() as s:
        history = await s.scalar(
            select(ProjectRoleHistory).where(
                ProjectRoleHistory.project_id == project.project_id,
                ProjectRoleHistory.role_title.ilike(role.role_name),
            )
        )

    assert history is not None
    assert history.user_id == actor.user_id


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_actor_assigns_unassigned_project_role_history(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Если роль присутствует, но не назначена (user_id=-1) — назначается актёр."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    actor = await create_user(request)

    await create_project_role(
        project_id=project.project_id,
        user_id=-1,
        role_title=role.role_name,
        request=request,
    )

    response = await put_role_actor(
        client, role.role_id, actor.user_id, auth_headers, request
    )
    assert response.status_code == status.HTTP_200_OK

    async with TestSession() as s:
        history = await s.scalar(
            select(ProjectRoleHistory).where(
                ProjectRoleHistory.project_id == project.project_id,
                ProjectRoleHistory.role_title.ilike(role.role_name),
            )
        )

    assert history is not None
    assert history.user_id == actor.user_id


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_actor_replaces_project_role_history(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Если роль уже назначена в ProjectRoleHistory — актёр заменяется."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    first_actor = await create_user(request)
    second_actor = await create_user(request)

    await create_project_role(
        project_id=project.project_id,
        user_id=first_actor.user_id,
        role_title=role.role_name,
        request=request,
    )

    response = await put_role_actor(
        client, role.role_id, second_actor.user_id, auth_headers, request
    )
    assert response.status_code == status.HTTP_200_OK

    async with TestSession() as s:
        history = await s.scalar(
            select(ProjectRoleHistory).where(
                ProjectRoleHistory.project_id == project.project_id,
                ProjectRoleHistory.role_title.ilike(role.role_name),
            )
        )

    assert history is not None
    assert history.user_id == second_actor.user_id

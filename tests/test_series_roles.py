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
from tests.helpers.roles import (
    create_record,
    create_role,
    delete_record,
    patch_role_note,
    patch_role_state,
    post_role,
    post_role_record,
    put_role_actor,
    put_role_subtitle,
)
from app.roles.models import Fix, Record, Role
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


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_set_role_null_actor_success(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Можно установить null в качестве актёра."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await put_role_actor(client, role.role_id, None, auth_headers, request)
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["user_id"] == None
    assert body["nickname"] == None
    assert body["avatar_url"] == None


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


# ===========================================================================
# PATCH /series/role/{role_id}/state
# ===========================================================================


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_update_role_state_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await client.patch("/series/role/9999/state", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_role_not_found(
    auth_headers: dict, client: AsyncClient
):
    """Несуществующая роль → 404."""
    response = await patch_role_state(client, 9999999, auth_headers, checked=True)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 403
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_update_role_state_forbidden_for_plain_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с серией/проектом → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await patch_role_state(client, role.role_id, auth_headers, checked=True)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 200 — access by level >= CURATOR_LEVEL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_ok_by_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня >= 2 может менять состояние роли."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await patch_role_state(client, role.role_id, auth_headers, checked=True)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 200 — access by project curator
# ---------------------------------------------------------------------------


async def test_update_role_state_ok_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) может менять состояние роли."""
    project_curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=project_curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    headers = await login_user(client, project_curator.nickname)

    response = await patch_role_state(client, role.role_id, headers, timed=True)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 200 — access by series curator
# ---------------------------------------------------------------------------


async def test_update_role_state_ok_by_series_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор серии (уровень 1) может менять состояние роли."""
    series_curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project_owner, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=project_owner.user_id, request=request)
    series = await create_series(
        project.project_id, request, curator=series_curator.user_id
    )
    role = await create_role(series.id, None, request)
    headers = await login_user(client, series_curator.nickname)

    response = await patch_role_state(client, role.role_id, headers, checked=True)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 200 — access by no_actors (staff members of the series)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "staff_field",
    [
        "curator",
        "sound_engineer",
        "raw_sound_engineer",
        "timer",
        "translator",
        "director",
    ],
)
async def test_update_role_state_ok_by_staff(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Таймер серии (no_actor) может менять состояние роли."""
    staff_user, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project_owner, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=project_owner.user_id, request=request)
    series = await create_series(
        project.project_id, request, **{staff_field: staff_user.user_id}
    )
    role = await create_role(series.id, None, request)
    headers = await login_user(client, staff_user.nickname)

    response = await patch_role_state(client, role.role_id, headers, timed=True)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Response shape and field updates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_response_shape(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Ответ содержит checked, timed, state."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await patch_role_state(client, role.role_id, auth_headers, checked=True)
    assert response.status_code == status.HTTP_200_OK
    assert set(response.json().keys()) == {"checked", "timed", "state"}


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_checked_is_persisted(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Флаг checked обновляется и возвращается корректно."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request, checked=False)

    response = await patch_role_state(client, role.role_id, auth_headers, checked=True)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["checked"] is True


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_timed_is_persisted(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Флаг timed обновляется и возвращается корректно."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request, timed=False)

    response = await patch_role_state(client, role.role_id, auth_headers, timed=True)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["timed"] is True


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_empty_payload_does_not_change_flags(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пустой payload не меняет флаги."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request, checked=True, timed=True)

    response = await patch_role_state(client, role.role_id, auth_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["checked"] is True
    assert body["timed"] is True


# ---------------------------------------------------------------------------
# State computation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_no_records_gives_not_loaded(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Нет записей → состояние 'не загружена' независимо от флагов."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await patch_role_state(
        client, role.role_id, auth_headers, checked=True, timed=True
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == "не загружена"


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_records_timed_false_gives_not_timed(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Есть записи, timed=False → состояние 'не затаймлена'."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    await create_record(role.role_id, request)

    response = await patch_role_state(
        client, role.role_id, auth_headers, timed=False, checked=True
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == "не затаймлена"


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_records_timed_true_checked_false_gives_not_checked(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Есть записи, timed=True, checked=False → состояние 'не проверена'."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    await create_record(role.role_id, request)

    response = await patch_role_state(
        client, role.role_id, auth_headers, timed=True, checked=False
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == "не проверена"


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_state_records_timed_checked_gives_mixing_ready(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Есть записи, timed=True, checked=True, нет фиксов → 'готова к сведению'."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    await create_record(role.role_id, request)

    response = await patch_role_state(
        client, role.role_id, auth_headers, timed=True, checked=True
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == "готова к сведению"


# ===========================================================================
# PUT /series/role/{role_id}/subtitle
# ===========================================================================


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_update_subtitle_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await put_role_subtitle(client, 9999, {})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_subtitle_role_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая роль → 404."""
    response = await put_role_subtitle(client, 9999999, auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_subtitle_invalid_extension(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Файл без расширения .srt → 400."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await client.put(
        f"/series/role/{role.role_id}/subtitle",
        files={"srt_file": ("subtitles.txt", b"content", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# 403 — SeriesDataAccessChecker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_update_subtitle_forbidden_for_unrelated_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с серией/проектом → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await put_role_subtitle(client, role.role_id, auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 200 — access by level >= CURATOR_LEVEL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_subtitle_success_by_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня >= 2 может обновить srt роли."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    response = await put_role_subtitle(
        client, role.role_id, auth_headers, request=request
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["subtitle"].endswith(".srt")
    assert body["checked"] is False
    assert isinstance(body["fixes"], list)
    assert len(body["fixes"]) == 1
    fix = body["fixes"][0]
    assert fix["phrase"] == 0
    assert "был обновлён srt файл" in fix["note"]
    assert fix["ready"] is False
    assert "state" in body


# ---------------------------------------------------------------------------
# 200 — access by project curator (level 1)
# ---------------------------------------------------------------------------


async def test_update_subtitle_success_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) может обновить srt роли."""
    curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)
    headers = await login_user(client, curator.nickname)

    response = await put_role_subtitle(client, role.role_id, headers, request=request)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 200 — access by staff_ids (parametrized по полю)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "staff_field",
    [
        "curator",
        "sound_engineer",
        "raw_sound_engineer",
        "director",
        "timer",
        "translator",
    ],
)
async def test_update_subtitle_success_by_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Каждый тип no_actors (staff) серии имеет доступ через SeriesDataAccessChecker."""
    staff_user, _ = await create_user_with_level(MEMBER_LEVEL, request)
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id, request, **{staff_field: staff_user.user_id}
    )
    role = await create_role(series.id, None, request)
    headers = await login_user(client, staff_user.nickname)

    response = await put_role_subtitle(client, role.role_id, headers, request=request)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Fix created, checked set to False, full fix list returned
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_subtitle_sets_checked_false(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """checked сбрасывается в False при обновлении srt, даже если был True."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request, checked=True)

    response = await put_role_subtitle(
        client, role.role_id, auth_headers, request=request
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["checked"] is False

    async with TestSession() as s:
        db_role = await s.get(Role, role.role_id)
        assert db_role is not None
        assert db_role.checked is False


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_subtitle_accumulates_fixes(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Каждый вызов добавляет ровно один Fix; список растёт."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    r1 = await put_role_subtitle(client, role.role_id, auth_headers, request=request)
    assert r1.status_code == status.HTTP_200_OK
    assert len(r1.json()["fixes"]) == 1

    r2 = await put_role_subtitle(client, role.role_id, auth_headers, request=request)
    assert r2.status_code == status.HTTP_200_OK
    assert len(r2.json()["fixes"]) == 2


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_subtitle_returns_full_fix_list(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Response содержит полный список фиксов, включая ранее существовавшие."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, None, request)

    async with TestSession() as s:
        pre_fix = Fix(role_id=role.role_id, phrase=5, note="старый фикс", ready=False)
        s.add(pre_fix)
        await s.commit()
        await s.refresh(pre_fix)

    pre_fix_id = pre_fix.id

    async def _delete_pre_fix() -> None:
        async with TestSession() as s:
            db_fix = await s.get(Fix, pre_fix_id)
            if db_fix:
                await s.delete(db_fix)
                await s.commit()

    request.addfinalizer(lambda: asyncio.run(_delete_pre_fix()))

    response = await put_role_subtitle(
        client, role.role_id, auth_headers, request=request
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body["fixes"]) == 2
    phrases = {f["phrase"] for f in body["fixes"]}
    assert 0 in phrases
    assert 5 in phrases


# ===========================================================================
# POST /series/role/{role_id}/records
# ===========================================================================


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_add_record_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await client.post(
        "/series/role/9999/records",
        data={"record_title": "test.wav"},
        files={"record_file": ("test.wav", b"data", "audio/wav")},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_add_record_role_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая роль → 404."""
    response = await post_role_record(client, 9999999, auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 403
# ---------------------------------------------------------------------------


async def test_add_record_forbidden_for_unrelated_member(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с серией/проектом → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)

    stranger, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, stranger.nickname)

    response = await post_role_record(client, role.role_id, headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 400 — invalid file format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_add_record_invalid_format(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Файл не wav/flac/mp3 → 400."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)

    response = await post_role_record(
        client,
        role.role_id,
        auth_headers,
        record_title="audio.ogg",
        content=b"data",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# 201 — access by level >= 2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_add_record_success_by_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня >= 2 может добавить запись."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)

    response = await post_role_record(
        client, role.role_id, auth_headers, request=request
    )
    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    assert "record" in body
    assert body["record"]["record_title"] == "test.wav"
    assert body["record"]["record_url"].startswith("/records/")
    assert body["record"]["record_note"] is None
    assert "state" in body
    # Роль перешла из NOT_LOADED → NOT_TIMED (нет тайминга)
    assert body["state"] == "не затаймлена"


# ---------------------------------------------------------------------------
# 201 — access by project curator (level 1)
# ---------------------------------------------------------------------------


async def test_add_record_success_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) может добавить запись."""
    curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    headers = await login_user(client, curator.nickname)

    response = await post_role_record(client, role.role_id, headers, request=request)
    assert response.status_code == status.HTTP_201_CREATED


# ---------------------------------------------------------------------------
# 201 — access by no_actor (series staff)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "staff_field",
    [
        "curator",
        "sound_engineer",
        "raw_sound_engineer",
        "director",
        "timer",
        "translator",
    ],
)
async def test_add_record_success_by_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник из no_actors (напр. sound_engineer серии) может добавить запись."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    staff_member, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(
        project.project_id,
        request,
        **{staff_field: staff_member.user_id},
    )
    role = await create_role(series.id, user_id=None, request=request)
    headers = await login_user(client, staff_member.nickname)

    response = await post_role_record(client, role.role_id, headers, request=request)
    assert response.status_code == status.HTTP_201_CREATED


# ---------------------------------------------------------------------------
# 201 — access by role actor (level 1)
# ---------------------------------------------------------------------------


async def test_add_record_success_by_role_actor(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр роли (уровень 1) может добавить запись в свою роль."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=actor.user_id, request=request)
    headers = await login_user(client, actor.nickname)

    response = await post_role_record(client, role.role_id, headers, request=request)
    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    assert body["state"] == "не затаймлена"


async def test_add_record_actor_cannot_upload_to_other_role(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр одной роли не может добавить запись в чужую роль."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    # Роль назначена другому актёру (None — не назначена)
    role = await create_role(series.id, user_id=None, request=request)
    headers = await login_user(client, actor.nickname)

    response = await post_role_record(client, role.role_id, headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_add_record_state_not_loaded_to_not_timed(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Первая запись переводит роль из NOT_LOADED → NOT_TIMED."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(
        series.id, user_id=None, request=request, timed=False, checked=False
    )

    response = await post_role_record(
        client, role.role_id, auth_headers, request=request
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["state"] == "не затаймлена"


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_add_record_resets_timed_and_checked_to_false(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Добавление записи сбрасывает timed и checked в False → состояние 'не затаймлена'."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    # Роль уже прошла все стадии: timed=True, checked=True
    role = await create_role(
        series.id, user_id=None, request=request, timed=True, checked=True
    )

    response = await post_role_record(
        client, role.role_id, auth_headers, request=request
    )
    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    assert body["state"] == "не затаймлена"

    async with TestSession() as s:
        db_role = await s.get(Role, role.role_id)
        assert db_role is not None
        assert db_role.timed is False
        assert db_role.checked is False


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_add_record_supports_flac_and_mp3(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Файлы .flac и .mp3 принимаются."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    for filename in ("audio.flac", "audio.mp3"):
        role = await create_role(series.id, user_id=None, request=request)
        response = await post_role_record(
            client,
            role.role_id,
            auth_headers,
            record_title=filename,
            content=b"\x00" * 16,
            request=request,
        )
        assert response.status_code == status.HTTP_201_CREATED, f"Failed for {filename}"
        assert response.json()["record"]["record_url"].endswith(
            filename.rsplit(".", 1)[-1]
        ), f"URL should end with extension for {filename}"


# ---------------------------------------------------------------------------
# Response fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "auth_headers, record_title, note",
    [
        ({"level": CURATOR_LEVEL}, "ep01.wav", None),
        ({"level": CURATOR_LEVEL}, "take2.flac", "хороший дубль"),
        ({"level": CURATOR_LEVEL}, "final.mp3", "финальный вариант"),
    ],
    indirect=["auth_headers"],
)
async def test_add_record_response_fields(
    auth_headers: dict,
    record_title: str,
    note: str | None,
    client: AsyncClient,
    request: pytest.FixtureRequest,
):
    """Проверяет все поля ответа POST /series/role/{role_id}/records."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)

    response = await post_role_record(
        client,
        role.role_id,
        auth_headers,
        record_title=record_title,
        record_note=note,
        request=request,
    )

    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()
    print(body)
    ext = record_title.rsplit(".", 1)[-1]

    # record — вложенный объект с полями записи
    record = body["record"]
    assert isinstance(record["id"], int) and record["id"] > 0
    assert record["record_title"] == record_title
    assert record["record_note"] == note
    assert record["record_url"].startswith("/records/")
    assert record["record_url"].endswith(f".{ext}")

    # state — всегда «не затаймлена»: timed сбрасывается при загрузке записи
    assert body["state"] == "не затаймлена"


# ===========================================================================
# DELETE /series/role/records/{record_id}
# ===========================================================================


# ---------------------------------------------------------------------------
# 401 — no auth
# ---------------------------------------------------------------------------


async def test_delete_record_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await client.delete("/series/role/records/9999999")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_record_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая запись → 404."""
    response = await delete_record(client, 9999999, auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 403 — random member without any link to the series
# ---------------------------------------------------------------------------


async def test_delete_record_forbidden_for_unrelated_member(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с ролью/серией не может удалить запись → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    stranger, _ = await create_user_with_level(MEMBER_LEVEL, request)

    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(role.role_id, request=request)

    headers = await login_user(client, stranger.nickname)
    response = await delete_record(client, record.id, headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 403 — actor of a different role cannot delete record of another role
# ---------------------------------------------------------------------------


async def test_delete_record_forbidden_for_actor_of_other_role(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр другой роли не может удалить запись чужой роли → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)

    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)

    other_role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(other_role.role_id, request=request)

    # actor is assigned to a different role, not other_role
    await create_role(series.id, user_id=actor.user_id, request=request)

    headers = await login_user(client, actor.nickname)
    response = await delete_record(client, record.id, headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 200 — curator (level >= CURATOR_LEVEL)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_record_success_by_curator(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор (уровень >= 2) может удалить любую запись."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(
        role.role_id
    )  # no request — we expect endpoint to delete

    response = await delete_record(client, record.id, auth_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "state" in body


# ---------------------------------------------------------------------------
# 200 — project curator
# ---------------------------------------------------------------------------


async def test_delete_record_success_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта может удалить запись."""
    curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(role.role_id)

    headers = await login_user(client, curator.nickname)
    response = await delete_record(client, record.id, headers)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 200 — staff member (no_actors field)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "staff_field",
    [
        "curator",
        "sound_engineer",
        "raw_sound_engineer",
        "director",
        "timer",
        "translator",
    ],
)
async def test_delete_record_success_by_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Любой no_actors (staff) серии может удалить запись."""
    project_curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    staff_member, _ = await create_user_with_level(MEMBER_LEVEL, request)

    project = await create_project(curator_id=project_curator.user_id, request=request)
    series = await create_series(
        project.project_id, request, **{staff_field: staff_member.user_id}
    )
    role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(role.role_id)

    headers = await login_user(client, staff_member.nickname)
    response = await delete_record(client, record.id, headers)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 200 — role actor
# ---------------------------------------------------------------------------


async def test_delete_record_success_by_role_actor(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр роли может удалить собственную запись."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)

    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=actor.user_id, request=request)
    record = await create_record(role.role_id)

    headers = await login_user(client, actor.nickname)
    response = await delete_record(client, record.id, headers)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# State transitions after deletion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_last_record_state_becomes_not_loaded(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Удаление последней записи → состояние роли NOT_LOADED (не загружена)."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(role.role_id)

    response = await delete_record(client, record.id, auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == "не загружена"


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_one_of_two_records_role_switches_to_not_timed(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Удаление одной из двух записей у готовой роли → состояние изменяется на не затаймлена."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(
        series.id, user_id=None, request=request, timed=True, checked=True
    )
    # two records
    record1 = await create_record(role.role_id)
    record2 = await create_record(role.role_id, request=request)  # this one stays

    change_state_result = await patch_role_state(
        client, role.role_id, auth_headers, checked=True, timed=True
    )
    assert change_state_result.status_code == status.HTTP_200_OK

    response = await delete_record(client, record1.id, auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == "не затаймлена"


# ---------------------------------------------------------------------------
# DB cleanup — record is actually removed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_record_removes_from_db(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """После удаления записи её нет в БД."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(role.role_id)
    record_id = record.id

    response = await delete_record(client, record.id, auth_headers)
    assert response.status_code == status.HTTP_200_OK

    async with TestSession() as s:
        db_record = await s.get(Record, record_id)
    assert db_record is None


# ---------------------------------------------------------------------------
# File deletion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_record_removes_file(
    auth_headers: dict,
    client: AsyncClient,
    request: pytest.FixtureRequest,
):
    """Физический файл записи удаляется вместе с записью."""
    from app.series.utils import RECORDS_ROOT

    # Create a real file in the records directory
    fake_file = RECORDS_ROOT / "test_delete_me.wav"
    fake_file.write_bytes(b"RIFF")

    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    record = await create_record(
        role.role_id, record_url=f"/records/test_delete_me.wav"
    )

    response = await delete_record(client, record.id, auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert not fake_file.exists(), "Файл должен быть удалён с диска"


# ===========================================================================
# PATCH /series/role/{role_id}/note
# ===========================================================================


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_update_role_note_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await client.patch("/series/role/9999/note", json={"note": "test"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_note_role_not_found(
    auth_headers: dict, client: AsyncClient
):
    """Несуществующая роль → 404."""
    response = await patch_role_note(client, 9999999, "text", auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 403
# ---------------------------------------------------------------------------


async def test_update_role_note_forbidden_for_unrelated_member(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с серией/проектом → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)

    stranger, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, stranger.nickname)

    response = await patch_role_note(client, role.role_id, "text", headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_update_role_note_forbidden_for_actor_of_other_role(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр другой роли → 403."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    headers = await login_user(client, actor.nickname)

    response = await patch_role_note(client, role.role_id, "text", headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 200 — access by level >= 2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_role_note_success_by_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня >= 2 может изменить пояснение."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)

    response = await patch_role_note(client, role.role_id, "новое пояснение", auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["note"] == "новое пояснение"


# ---------------------------------------------------------------------------
# 200 — access by project curator (level 1)
# ---------------------------------------------------------------------------


async def test_update_role_note_success_by_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) может изменить пояснение."""
    curator, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=None, request=request)
    headers = await login_user(client, curator.nickname)

    response = await patch_role_note(client, role.role_id, "куратор пишет", headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["note"] == "куратор пишет"


# ---------------------------------------------------------------------------
# 200 — access by no_actors (series staff)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "staff_field",
    [
        "curator",
        "sound_engineer",
        "raw_sound_engineer",
        "director",
        "timer",
        "translator",
    ],
)
async def test_update_role_note_success_by_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник из no_actors серии может изменить пояснение."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    staff_member, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(
        project.project_id,
        request,
        **{staff_field: staff_member.user_id},
    )
    role = await create_role(series.id, user_id=None, request=request)
    headers = await login_user(client, staff_member.nickname)

    response = await patch_role_note(client, role.role_id, "staff note", headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["note"] == "staff note"


# ---------------------------------------------------------------------------
# 200 — access by role actor
# ---------------------------------------------------------------------------


async def test_update_role_note_success_by_role_actor(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр своей роли может изменить пояснение."""
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    role = await create_role(series.id, user_id=actor.user_id, request=request)
    headers = await login_user(client, actor.nickname)

    response = await patch_role_note(client, role.role_id, "актёр пишет", headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["note"] == "актёр пишет"

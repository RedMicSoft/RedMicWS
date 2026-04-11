"""
Tests for DELETE /series/role/{role_id}
"""

import pytest
from httpx import AsyncClient
from fastapi import status

from tests.conftest import TestSession
from tests.helpers.users import create_user_with_level, login_user
from tests.helpers.projects import create_project
from tests.helpers.series import create_series
from tests.helpers.roles import create_role
from app.roles.models import Role
from app.users.utils import MEMBER_LEVEL, CURATOR_LEVEL


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
    role = await create_role(series.id, -1, request)

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
    role = await create_role(series.id, -1)

    response = await client.delete(f"/series/role/{role.role_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "Роль успешно удалена из серии"

    # убеждаемся, что роль действительно удалена
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
    role = await create_role(series.id, -1)
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
    role = await create_role(series.id, -1)
    headers = await login_user(client, series_curator.nickname)

    response = await client.delete(f"/series/role/{role.role_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "Роль успешно удалена из серии"

    async with TestSession() as s:
        assert await s.get(Role, role.role_id) is None

"""
Tests for PUT /series/{seria_id}/subs and POST /series/{seria_id}/subs/fix
"""

import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from fastapi import status

from tests.conftest import TestSession
from tests.helpers.users import create_user_with_level, login_user
from tests.helpers.projects import create_project
from tests.helpers.series import create_series
from tests.helpers.roles import create_role
from tests.helpers.subs import subs_put, subs_fix_post
from app.projects.models import ProjectUser
from app.roles.models import Fix, Role
from app.series.utils import MEDIA_ROOT
from app.users.utils import MEMBER_LEVEL, CURATOR_LEVEL

_DATA = Path(__file__).parent / "data"
_BY_NAME = _DATA / "subs_update_by_name.ass"
_BY_STYLE = _DATA / "subs_update_by_style.ass"

# Роли, ожидаемые при разборе по Name из subs_update_by_name.ass
_EXPECTED_ROLES_BY_NAME = {
    "Ales",
    "Fiery",
    "Мираша",
    "Надпись",
    "Rian",
    "Sebner_TV",
    "Староста",
    "l_Luna",
}

# ---------------------------------------------------------------------------
# Auth / access
# ---------------------------------------------------------------------------


async def test_subs_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await subs_put(client, 9999, _BY_NAME, "name", {})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_series_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая серия → 404."""
    response = await subs_put(client, 9999999, _BY_NAME, "name", auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_subs_forbidden_for_non_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с проектом/серией → 403."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_put(client, series.id, _BY_NAME, "name", auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_invalid_file_extension(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Файл без расширения .ass → 400."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.put(
        f"/series/{series.id}/subs",
        data={"parse_type": "name"},
        files={"ass_file": ("subtitles.txt", b"not an ass file", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# New roles creation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_create_new_roles_by_name(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """
    Загрузка ASS с parse_type=name: роли берутся из поля Name.
    Проверяем: все ожидаемые роли созданы, AssFile-записи добавлены,
    ass_url серии обновлён.
    """
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_put(client, series.id, _BY_NAME, "name", auth_headers, request)

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert str(data["ass_file"]["ass_file_url"]).startswith("/media/ass/")

    created_names = {r["role_name"] for r in data["roles"]}
    assert _EXPECTED_ROLES_BY_NAME == created_names

    for role in data["roles"]:
        assert str(role["subtitle"]).startswith("/media/srt/")

    # AssFile-записи (по одной на роль) присутствуют
    assert len(data["ass_file"]["ass_fixes"]) == len(_EXPECTED_ROLES_BY_NAME)
    fix_notes = [str(af["fix_note"]) for af in data["ass_file"]["ass_fixes"]]
    assert all(note.startswith("Добавлена роль:") for note in fix_notes)


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_create_new_roles_by_style(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """
    Загрузка ASS с parse_type=style: роли берутся из поля Style.
    В subs_update_by_name.ass стили: Основной, Курсив, Основной-сверху.
    """
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_put(client, series.id, _BY_NAME, "style", auth_headers, request)

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    style_names = {r["role_name"] for r in data["roles"]}
    assert style_names == {"Основной", "Курсив", "Основной-сверху"}
    assert style_names != _EXPECTED_ROLES_BY_NAME


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_create_roles_by_style_ass_file(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """
    Загрузка subs_update_by_style.ass (MLP) с parse_type=style:
    убеждаемся, что роли содержат имена стилей из этого файла.
    """
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_put(client, series.id, _BY_STYLE, "style", auth_headers, request)

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    role_names = {r["role_name"] for r in data["roles"]}
    assert role_names == {"Twilight", "Spike", "ms Cake", "Mayor", "Фон_ж_1", "SB"}


# ---------------------------------------------------------------------------
# Update: existing roles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_update_changed_role_creates_fix(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """
    Если SRT-содержимое роли изменилось между загрузками:
    - создаётся Fix с пометкой «обновлён srt файл»
    - checked роли сбрасывается в False
    - для роли с неизменённым SRT Fix не создаётся
    """
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    r1 = await subs_put(client, series.id, _BY_NAME, "name", auth_headers, request)
    assert r1.status_code == status.HTTP_200_OK, r1.text

    # Берём role_id и srt_url Fiery и Ales из БД
    async with TestSession() as s:
        db_fiery = await s.scalar(
            select(Role).where(Role.series_id == series.id, Role.role_name == "Fiery")
        )
        assert db_fiery is not None
        fiery_role_id = db_fiery.role_id
        fiery_srt_url = db_fiery.srt_url

        ales_role = await s.scalar(
            select(Role).where(Role.series_id == series.id, Role.role_name == "Ales")
        )
        assert ales_role is not None
        ales_role_id = ales_role.role_id

    # Подменяем SRT Fiery на диске — гарантируем отличие при следующей загрузке
    srt_path = MEDIA_ROOT.parent / fiery_srt_url.lstrip("/")
    srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nMODIFIED SENTINEL\n\n", "utf-8")

    # Выставляем checked=True, чтобы убедиться, что он сбросится
    async with TestSession() as s:
        db_fiery = await s.get(Role, fiery_role_id)
        assert db_fiery is not None
        db_fiery.checked = True
        await s.commit()

    r2 = await subs_put(client, series.id, _BY_NAME, "name", auth_headers, request)
    assert r2.status_code == status.HTTP_200_OK, r2.text

    # Проверяем Fix в БД напрямую
    async with TestSession() as s:
        fiery_fixes = (
            await s.scalars(select(Fix).where(Fix.role_id == fiery_role_id))
        ).all()
        ales_fixes = (
            await s.scalars(select(Fix).where(Fix.role_id == ales_role_id))
        ).all()

    assert len(fiery_fixes) >= 1, "Fix для Fiery не создан после изменения SRT"
    assert any("обновлён srt файл" in f.note for f in fiery_fixes)
    assert len(ales_fixes) == 0, "Fix для Ales не должен создаваться — SRT не менялся"

    # checked сброшен в ответе
    fiery_resp = next(r for r in r2.json()["roles"] if r["role_name"] == "Fiery")
    assert fiery_resp["checked"] is False


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_update_same_content_no_new_fix(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """
    Повторная загрузка того же ASS без изменений:
    новые Fix-записи не создаются, checked не сбрасывается.
    """
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    r1 = await subs_put(client, series.id, _BY_NAME, "name", auth_headers, request)
    assert r1.status_code == status.HTTP_200_OK, r1.text

    async with TestSession() as s:
        roles = (await s.scalars(select(Role).where(Role.series_id == series.id))).all()
        for role in roles:
            role.checked = True
        await s.commit()

    r2 = await subs_put(client, series.id, _BY_NAME, "name", auth_headers, request)
    assert r2.status_code == status.HTTP_200_OK, r2.text

    for role in r2.json()["roles"]:
        assert role["fixes"] == [], f"Неожиданный Fix у роли {role['role_name']}"
        assert role["checked"] is True, f"checked сброшен у роли {role['role_name']}"


# ---------------------------------------------------------------------------
# Actor assignment from project roles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_actor_assigned_from_project_role(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """
    Если в проекте есть ProjectRoleHistory с role_title совпадающим по имени с ролью в ASS,
    новая роль создаётся с user_id этого актёра.
    """
    from app.projects.models import ProjectRoleHistory

    actor, _ = await create_user_with_level(MEMBER_LEVEL, request)
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)

    async with TestSession() as s:
        proj_role = ProjectRoleHistory(
            project_id=project.project_id,
            role_title="Ales",
            user_id=actor.user_id,
            image_url="",
        )
        s.add(proj_role)
        await s.commit()
        await s.refresh(proj_role)
        proj_role_id = proj_role.role_id

    async def _delete_proj_role() -> None:
        async with TestSession() as s:
            db_pr = await s.get(ProjectRoleHistory, proj_role_id)
            if db_pr:
                await s.delete(db_pr)
            await s.commit()

    request.addfinalizer(lambda: asyncio.run(_delete_proj_role()))

    response = await subs_put(client, series.id, _BY_NAME, "name", auth_headers, request)
    assert response.status_code == status.HTTP_200_OK, response.text

    ales_role = next(r for r in response.json()["roles"] if r["role_name"] == "Ales")
    assert ales_role["actor"] is not None
    assert ales_role["actor"]["user_id"] == actor.user_id


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_no_project_role_actor_is_none(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """
    Если в проекте нет записи ProjectRoleHistory для роли — actor в ответе None.
    """
    curator, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_put(client, series.id, _BY_NAME, "name", auth_headers, request)
    assert response.status_code == status.HTTP_200_OK, response.text

    for role in response.json()["roles"]:
        assert role["actor"] is None, f"Неожиданный актёр у роли {role['role_name']}"


# ---------------------------------------------------------------------------
# Access control: все категории участников проекта
#
# SubsAccessChecker пропускает пользователя если выполняется хотя бы одно:
#   1. user_level >= CURATOR_LEVEL                 (уже покрыто основными тестами)
#   2. user_id == project.curator_id               → test_subs_access_project_curator
#   3. запись в ProjectUser для этого проекта      → test_subs_access_project_participant
#   4. user_id в series.staff_ids (6 полей)        → test_subs_access_series_staff
#   5. user_id среди актёров серии (Role)          → test_subs_access_series_actor
# ---------------------------------------------------------------------------


async def test_subs_access_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (без уровня куратора) имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    project = await create_project(curator_id=requester.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_put(client, series.id, _BY_NAME, "name", headers, request)
    assert response.status_code == status.HTTP_200_OK


async def test_subs_access_project_participant(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник проекта (запись в ProjectUser) имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    async with TestSession() as s:
        s.add(ProjectUser(user_id=requester.user_id, project_id=project.project_id))
        await s.commit()

    async def _remove_participant() -> None:
        async with TestSession() as s:
            pu = await s.get(ProjectUser, (requester.user_id, project.project_id))
            if pu:
                await s.delete(pu)
            await s.commit()

    request.addfinalizer(lambda: asyncio.run(_remove_participant()))

    response = await subs_put(client, series.id, _BY_NAME, "name", headers, request)
    assert response.status_code == status.HTTP_200_OK


_STAFF_FIELDS = [
    "curator",
    "sound_engineer",
    "raw_sound_engineer",
    "timer",
    "translator",
    "director",
]


@pytest.mark.parametrize("staff_field", _STAFF_FIELDS)
async def test_subs_access_series_staff(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Каждый из шести стафф-участников серии имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id, request, **{staff_field: requester.user_id}
    )

    response = await subs_put(client, series.id, _BY_NAME, "name", headers, request)
    assert response.status_code == status.HTTP_200_OK


async def test_subs_access_series_actor(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр серии (запись в Role) имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    await create_role(series.id, requester.user_id, request)

    response = await subs_put(client, series.id, _BY_NAME, "name", headers, request)
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# POST /series/{seria_id}/subs/fix
# ---------------------------------------------------------------------------


async def test_subs_fix_requires_auth(client: AsyncClient):
    """Без токена → 401."""
    response = await subs_fix_post(client, 9999, "текст фикса", {})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_fix_series_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая серия → 404."""
    response = await subs_fix_post(client, 9999999, "текст фикса", auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_subs_fix_forbidden_for_non_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с проектом/серией → 403."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_fix_post(client, series.id, "текст фикса", auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_fix_creates_fix(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Успешное создание фикса: ответ содержит fix_id и fix_note, статус 201."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    fix_note = "поправить синхронизацию реплики 5"
    response = await subs_fix_post(client, series.id, fix_note, auth_headers, request)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()
    assert data["fix_note"] == fix_note
    assert isinstance(data["fix_id"], int)


# ---------------------------------------------------------------------------
# Access control для POST /subs/fix: те же категории, что и в PUT /subs
#
# SubsAccessChecker пропускает если хотя бы одно:
#   1. user_level >= CURATOR_LEVEL                 → test_subs_fix_creates_fix
#   2. user_id == project.curator_id               → test_subs_fix_access_project_curator
#   3. запись в ProjectUser для этого проекта      → test_subs_fix_access_project_participant
#   4. user_id в series.staff_ids (6 полей)        → test_subs_fix_access_series_staff
#   5. user_id среди актёров серии (Role)          → test_subs_fix_access_series_actor
# ---------------------------------------------------------------------------


async def test_subs_fix_access_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (без уровня куратора) имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    project = await create_project(curator_id=requester.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await subs_fix_post(client, series.id, "фикс", headers, request)
    assert response.status_code == status.HTTP_201_CREATED


async def test_subs_fix_access_project_participant(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник проекта (запись в ProjectUser) имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    async with TestSession() as s:
        s.add(ProjectUser(user_id=requester.user_id, project_id=project.project_id))
        await s.commit()

    async def _remove_participant() -> None:
        async with TestSession() as s:
            pu = await s.get(ProjectUser, (requester.user_id, project.project_id))
            if pu:
                await s.delete(pu)
            await s.commit()

    request.addfinalizer(lambda: asyncio.run(_remove_participant()))

    response = await subs_fix_post(client, series.id, "фикс", headers, request)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize("staff_field", _STAFF_FIELDS)
async def test_subs_fix_access_series_staff(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Каждый из шести стафф-участников серии имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id, request, **{staff_field: requester.user_id}
    )

    response = await subs_fix_post(client, series.id, "фикс", headers, request)
    assert response.status_code == status.HTTP_201_CREATED


async def test_subs_fix_access_series_actor(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Актёр серии (запись в Role) имеет доступ."""
    requester, _ = await create_user_with_level(MEMBER_LEVEL, request)
    headers = await login_user(client, requester.nickname)

    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    await create_role(series.id, requester.user_id, request)

    response = await subs_fix_post(client, series.id, "фикс", headers, request)
    assert response.status_code == status.HTTP_201_CREATED

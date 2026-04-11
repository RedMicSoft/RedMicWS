"""
Tests for PUT /series/{seria_id}/subs
"""

import asyncio
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from fastapi import status

from tests.conftest import TestSession
from tests.helpers.users import create_user_with_level, login_user
from tests.helpers.projects import create_project
from tests.helpers.series import create_series
from app.series.models import AssFile
from app.roles.models import Fix, Role
from app.series.utils import MEDIA_ROOT
from app.users.utils import MEMBER_LEVEL, CURATOR_LEVEL

_DATA = Path(__file__).parent / "data"
_BY_NAME = _DATA / "subs_update_by_name.ass"
_BY_NAME_MODIFIED = _DATA / "subs_update_by_name_modified.ass"
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
# Helpers
# ---------------------------------------------------------------------------


def _cleanup_response_files(response_json: dict) -> None:
    """Удаляет ASS и SRT файлы, созданные эндпоинтом."""
    urls: list[str] = []
    ass_url = response_json.get("ass_file", {}).get("ass_file_url")
    if ass_url:
        urls.append(ass_url)
    for role in response_json.get("roles", []):
        srt = role.get("subtitle")
        if srt:
            urls.append(srt)
    for url in urls:
        path = MEDIA_ROOT.parent / url.lstrip("/")
        if path.exists():
            path.unlink()


async def _subs_put(
    client: AsyncClient,
    seria_id: int,
    ass_path: Path,
    parse_type: str,
    headers: dict,
) -> httpx.Response:
    with ass_path.open("rb") as f:
        return await client.put(
            f"/series/{seria_id}/subs",
            data={"parse_type": parse_type},
            files={"ass_file": (ass_path.name, f, "text/plain")},
            headers=headers,
        )


# ---------------------------------------------------------------------------
# Auth / access
# ---------------------------------------------------------------------------


async def test_subs_requires_auth(client: AsyncClient, request: pytest.FixtureRequest):
    """Без токена → 401."""
    # Используем dummy seria_id; отказ должен произойти до любой обработки файла.
    with _BY_NAME.open("rb") as f:
        response = await client.put(
            "/series/9999/subs",
            data={"parse_type": "name"},
            files={"ass_file": (_BY_NAME.name, f, "text/plain")},
        )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_subs_series_not_found(auth_headers: dict, client: AsyncClient):
    """Несуществующая серия → 404."""
    with _BY_NAME.open("rb") as f:
        response = await client.put(
            "/series/9999999/subs",
            data={"parse_type": "name"},
            files={"ass_file": (_BY_NAME.name, f, "text/plain")},
            headers=auth_headers,
        )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_subs_forbidden_for_non_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник без связи с проектом/серией → 403."""
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    with _BY_NAME.open("rb") as f:
        response = await client.put(
            f"/series/{series.id}/subs",
            data={"parse_type": "name"},
            files={"ass_file": (_BY_NAME.name, f, "text/plain")},
            headers=auth_headers,
        )
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

    fake_content = b"not an ass file"
    response = await client.put(
        f"/series/{series.id}/subs",
        data={"parse_type": "name"},
        files={"ass_file": ("subtitles.txt", fake_content, "text/plain")},
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

    response = await _subs_put(client, series.id, _BY_NAME, "name", auth_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    request.addfinalizer(lambda: _cleanup_response_files(data))

    # ass_url задан
    assert str(data["ass_file"]["ass_file_url"]).startswith("/media/ass/")

    # все ожидаемые роли созданы
    created_names = {r["role_name"] for r in data["roles"]}
    assert _EXPECTED_ROLES_BY_NAME == created_names

    # каждая роль имеет srt_url
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
    Убеждаемся, что набор ролей отличается от результата name-парсинга.
    """
    other, _ = await create_user_with_level(CURATOR_LEVEL, request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await _subs_put(client, series.id, _BY_NAME, "style", auth_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    request.addfinalizer(lambda: _cleanup_response_files(data))

    style_names = {r["role_name"] for r in data["roles"]}
    # стили из ASS: Основной, Курсив, Основной-сверху
    assert style_names == {"Основной", "Курсив", "Основной-сверху"}
    # это не то же самое, что по Name
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

    response = await _subs_put(client, series.id, _BY_STYLE, "style", auth_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    request.addfinalizer(lambda: _cleanup_response_files(data))

    role_names = {r["role_name"] for r in data["roles"]}

    # Стили, фактически используемые в диалогах MLP ASS
    _EXPECTED_ROLES_BY_STYLE = {
        "Twilight",
        "Spike",
        "ms Cake",
        "Mayor",
        "Фон_ж_1",
        "SB",
    }
    assert role_names == _EXPECTED_ROLES_BY_STYLE


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

    # Первая загрузка — создаём роли
    r1 = await _subs_put(client, series.id, _BY_NAME, "name", auth_headers)
    assert r1.status_code == status.HTTP_200_OK, r1.text
    request.addfinalizer(lambda: _cleanup_response_files(r1.json()))

    # Берём role_id и srt_url роли Fiery из БД
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
    srt_path.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nMODIFIED SENTINEL\n\n", "utf-8"
    )

    # Вручную выставим checked=True для Fiery, чтобы убедиться, что он сбросится
    async with TestSession() as s:
        db_fiery = await s.get(Role, fiery_role_id)
        if db_fiery is None:
            pytest.fail("Роль Fiery не найдена в БД после первой загрузки")
        db_fiery.checked = True
        await s.commit()

    # Вторая загрузка того же ASS
    r2 = await _subs_put(client, series.id, _BY_NAME, "name", auth_headers)
    assert r2.status_code == status.HTTP_200_OK, r2.text
    data2 = r2.json()
    request.addfinalizer(lambda: _cleanup_response_files(data2))

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

    # Дополнительно: checked сброшен в ответе
    fiery_resp = next(r for r in data2["roles"] if r["role_name"] == "Fiery")
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

    # Первая загрузка
    r1 = await _subs_put(client, series.id, _BY_NAME, "name", auth_headers)
    assert r1.status_code == status.HTTP_200_OK, r1.text
    request.addfinalizer(lambda: _cleanup_response_files(r1.json()))

    # Вручную выставим checked=True для нескольких ролей
    async with TestSession() as s:
        roles = (await s.scalars(select(Role).where(Role.series_id == series.id))).all()
        for role in roles:
            role.checked = True
        await s.commit()

    # Вторая загрузка — тот же файл
    r2 = await _subs_put(client, series.id, _BY_NAME, "name", auth_headers)
    assert r2.status_code == status.HTTP_200_OK, r2.text
    data2 = r2.json()
    request.addfinalizer(lambda: _cleanup_response_files(data2))

    # У всех ролей по-прежнему нет Fix-записей и checked=True
    for role in data2["roles"]:
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

    # Добавляем запись в ProjectRoleHistory: роль Ales → наш актёр
    proj_role_id: int
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

    response = await _subs_put(client, series.id, _BY_NAME, "name", auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    request.addfinalizer(lambda: _cleanup_response_files(data))

    ales_role = next(r for r in data["roles"] if r["role_name"] == "Ales")
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

    response = await _subs_put(client, series.id, _BY_NAME, "name", auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    request.addfinalizer(lambda: _cleanup_response_files(data))

    for role in data["roles"]:
        assert role["actor"] is None, f"Неожиданный актёр у роли {role['role_name']}"

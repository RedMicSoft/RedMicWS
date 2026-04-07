import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from fastapi import status

from tests.conftest import TestSession
from tests.helpers.users import create_user, create_user_with_level, login_user
from tests.helpers.projects import create_project
from tests.helpers.series import (
    create_series,
    create_material,
    create_series_link,
    STAFF_WORK_TYPES,
)
from tests.helpers.roles import create_role
from app.files.models import FileModel
from app.roles.models import RoleState
from app.series.models import SeriesState
from app.users.utils import MEMBER_LEVEL, CURATOR_LEVEL


async def _cleanup_material_file(material_link: str) -> None:
    filename = material_link.split("/")[-1]
    file_path = Path("team_files") / filename
    if file_path.exists():
        file_path.unlink()
    async with TestSession() as s:
        db_file = await s.scalar(select(FileModel).where(FileModel.file_url == material_link))
        if db_file:
            await s.delete(db_file)
            await s.commit()


async def _cleanup_series_link(link_id: int) -> None:
    from app.series.models import SeriesLink

    async with TestSession() as s:
        db_link = await s.get(SeriesLink, link_id)
        if db_link:
            await s.delete(db_link)
            await s.commit()


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_existing_series_endpoint(auth_headers: dict, client: AsyncClient):
    response = await client.get("/series/", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /series/user/{user_id}/work
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_all_positions_and_roles(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    worker = await create_user(request)
    project = await create_project(curator_id=worker.user_id, request=request)
    series = await create_series(
        project.project_id,
        request,
        curator=worker.user_id,
        sound_engineer=worker.user_id,
        raw_sound_engineer=worker.user_id,
        timer=worker.user_id,
        translator=worker.user_id,
        director=worker.user_id,
    )
    await create_role(series.id, worker.user_id, request)
    await create_role(series.id, worker.user_id, request)

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
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


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_across_two_projects(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    worker = await create_user(request)
    other = await create_user(request)

    project1 = await create_project(curator_id=other.user_id, request=request)
    series1 = await create_series(project1.project_id, request)
    await create_role(series1.id, worker.user_id, request)

    project2 = await create_project(curator_id=other.user_id, request=request)
    series2 = await create_series(project2.project_id, request, curator=worker.user_id)

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
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


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_empty_when_no_assignments(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    worker = await create_user(request)

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


async def test_work_requires_auth(client: AsyncClient):
    response = await client.get("/series/user/1/work")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_role_is_ready_flag(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """role_is_ready=True только у роли в состоянии MIXING_READY."""
    worker = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    await create_role(series.id, worker.user_id, request, state=RoleState.MIXING_READY)
    await create_role(series.id, worker.user_id, request, state=RoleState.NOT_LOADED)

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2

    ready = [i for i in data if i["role_is_ready"]]
    not_ready = [i for i in data if not i["role_is_ready"]]
    assert len(ready) == 1
    assert len(not_ready) == 1
    assert ready[0]["role"]["state"] == RoleState.MIXING_READY.value


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_subs_flag(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """subs=True если у серии задан ass_url, иначе False."""
    worker = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)

    series_with_ass = await create_series(
        project.project_id,
        request,
        curator=worker.user_id,
        ass_url="/media/subs/test.ass",
    )
    series_without_ass = await create_series(
        project.project_id,
        request,
        sound_engineer=worker.user_id,
        ass_url=None,
    )

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    by_seria = {item["seria"]["seria_id"]: item for item in data}
    assert by_seria[series_with_ass.id]["subs"] is True
    assert by_seria[series_without_ass.id]["subs"] is False


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_staff_role_is_ready_is_false(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Для всех должностей (не актёр) role_is_ready всегда False."""
    worker = await create_user(request)
    project = await create_project(curator_id=worker.user_id, request=request)
    await create_series(
        project.project_id,
        request,
        curator=worker.user_id,
        sound_engineer=worker.user_id,
    )

    response = await client.get(
        f"/series/user/{worker.user_id}/work", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    for item in response.json():
        assert item["role_is_ready"] is False


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_user_not_found(auth_headers: dict, client: AsyncClient):
    response = await client.get("/series/user/999999/work", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# DELETE /series/{seria_id}
# ---------------------------------------------------------------------------


async def test_delete_series_no_auth(client: AsyncClient):
    response = await client.delete("/series/999999")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_delete_series_not_found(auth_headers: dict, client: AsyncClient):
    response = await client.delete("/series/999999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_delete_series_forbidden_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.delete(f"/series/{series.id}", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_series_ok_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.delete(f"/series/{series.id}", headers=auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_delete_series_ok_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    curator, level = await create_user_with_level(
        access_level=MEMBER_LEVEL, request=request
    )
    project = await create_project(curator_id=curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    headers = await login_user(client, curator.nickname)

    response = await client.delete(f"/series/{series.id}", headers=headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT


# ---------------------------------------------------------------------------
# PATCH /series/{seria_id}/data
# ---------------------------------------------------------------------------


async def test_update_series_data_no_auth(client: AsyncClient):
    response = await client.patch("/series/999999/data", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_not_found(auth_headers: dict, client: AsyncClient):
    response = await client.patch("/series/999999/data", json={}, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_update_series_data_forbidden_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, не входящий в состав серии, получает 403."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/data", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_ok_full(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор (уровень 2) обновляет все поля сразу."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    payload = {
        "seria_title": "Обновлённое название",
        "start_date": "01.03.25",
        "first_stage_date": "02.03.25",
        "second_stage_date": "03.03.25",
        "publication_date": "04.03.25",
        "note": "Примечание к серии",
        "state": SeriesState.MIXING.value,
    }
    response = await client.patch(
        f"/series/{series.id}/data", json=payload, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["seria_title"] == "Обновлённое название"
    assert data["start_date"] == "2025-03-01"
    assert data["first_stage_date"] == "2025-03-02"
    assert data["second_stage_date"] == "2025-03-03"
    assert data["publication_date"] == "2025-03-04"
    assert data["note"] == "Примечание к серии"
    assert data["state"] == SeriesState.MIXING.value


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_ok_partial(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Частичное обновление: изменяется только note, остальные поля не трогаются."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, note="старое")

    response = await client.patch(
        f"/series/{series.id}/data",
        json={"note": "новое"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["note"] == "новое"
    assert data["seria_title"] == series.title  # не изменился


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_ok_empty_body(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пустое тело — значения серии остаются прежними, ответ содержит все поля."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id, request, state=SeriesState.VOICE_OVER
    )

    response = await client.patch(
        f"/series/{series.id}/data", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["seria_title"] == series.title
    assert data["state"] == SeriesState.VOICE_OVER.value


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_response_shape(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Ответ содержит ровно те поля, что описаны в контракте."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/data", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert set(response.json().keys()) == {
        "seria_title",
        "start_date",
        "first_stage_date",
        "second_stage_date",
        "publication_date",
        "note",
        "state",
    }


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
async def test_update_series_data_ok_as_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, назначенный на любую должность серии, может изменить данные."""
    staff_user, _ = await create_user_with_level(
        access_level=MEMBER_LEVEL, request=request
    )
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id, request, **{staff_field: staff_user.user_id}
    )
    headers = await login_user(client, staff_user.nickname)

    response = await client.patch(
        f"/series/{series.id}/data",
        json={"note": f"изменено через {staff_field}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["note"] == f"изменено через {staff_field}"


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_invalid_date_iso_format(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """ISO-формат даты (ГГГГ-ММ-ДД) не принимается — ожидается ДД.ММ.ГГ."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/data",
        json={"start_date": "2025-01-15"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_invalid_date_nonsense(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Произвольная строка вместо даты возвращает 422."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/data",
        json={"first_stage_date": "не дата"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# PATCH /series/{seria_id}/noactors
# ---------------------------------------------------------------------------

NOACTORS_KEYS = {"curator", "sound_engineer", "raw_sound_engineer", "director", "timer", "subtitler"}
PARTICIPANT_KEYS = {"user_id", "nickname", "avatar_url", "is_active"}


async def test_update_noactors_no_auth(client: AsyncClient):
    response = await client.patch("/series/999999/noactors", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_not_found(auth_headers: dict, client: AsyncClient):
    response = await client.patch("/series/999999/noactors", json={}, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_update_noactors_forbidden_plain_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, не являющийся куратором серии или проекта, получает 403."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, curator=other.user_id)

    response = await client.patch(
        f"/series/{series.id}/noactors", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_ok_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пользователь уровня 2 имеет доступ без привязки к серии."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/noactors", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK


async def test_update_noactors_ok_series_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор серии (уровень 1) имеет доступ к ручке."""
    series_curator, _ = await create_user_with_level(access_level=MEMBER_LEVEL, request=request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, curator=series_curator.user_id)
    headers = await login_user(client, series_curator.nickname)

    response = await client.patch(f"/series/{series.id}/noactors", json={}, headers=headers)
    assert response.status_code == status.HTTP_200_OK


async def test_update_noactors_ok_project_curator(
    client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор проекта (уровень 1) имеет доступ к ручке."""
    project_curator, _ = await create_user_with_level(access_level=MEMBER_LEVEL, request=request)
    project = await create_project(curator_id=project_curator.user_id, request=request)
    series = await create_series(project.project_id, request)
    headers = await login_user(client, project_curator.nickname)

    response = await client.patch(f"/series/{series.id}/noactors", json={}, headers=headers)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_response_shape(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Ответ содержит ровно 6 ключей, каждый — объект участника или null."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/noactors", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert set(data.keys()) == NOACTORS_KEYS
    for value in data.values():
        if value is not None:
            assert set(value.keys()) == PARTICIPANT_KEYS


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_empty_body_no_changes(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Пустое тело не изменяет участников серии."""
    worker = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, curator=worker.user_id)

    response = await client.patch(
        f"/series/{series.id}/noactors", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["curator"] is not None
    assert data["curator"]["user_id"] == worker.user_id


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_all_fields(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Обновление всех 6 полей одновременно."""
    u1 = await create_user(request)
    u2 = await create_user(request)
    u3 = await create_user(request)
    u4 = await create_user(request)
    u5 = await create_user(request)
    u6 = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    payload = {
        "curator": u1.user_id,
        "sound_engineer": u2.user_id,
        "raw_sound_engineer": u3.user_id,
        "director": u4.user_id,
        "timer": u5.user_id,
        "subtitler": u6.user_id,
    }
    response = await client.patch(
        f"/series/{series.id}/noactors", json=payload, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["curator"]["user_id"] == u1.user_id
    assert data["sound_engineer"]["user_id"] == u2.user_id
    assert data["raw_sound_engineer"]["user_id"] == u3.user_id
    assert data["director"]["user_id"] == u4.user_id
    assert data["timer"]["user_id"] == u5.user_id
    assert data["subtitler"]["user_id"] == u6.user_id


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_partial_fields(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Обновление части полей не затрагивает остальные."""
    worker = await create_user(request)
    new_engineer = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id, request, curator=worker.user_id, sound_engineer=worker.user_id
    )

    response = await client.patch(
        f"/series/{series.id}/noactors",
        json={"sound_engineer": new_engineer.user_id},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["sound_engineer"]["user_id"] == new_engineer.user_id
    assert data["curator"]["user_id"] == worker.user_id  # не изменился


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_set_field_to_null(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Явная передача null очищает поле."""
    worker = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, sound_engineer=worker.user_id)

    response = await client.patch(
        f"/series/{series.id}/noactors",
        json={"sound_engineer": None},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["sound_engineer"] is None


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_null_not_same_as_absent(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """null очищает поле, а отсутствие поля в теле — нет."""
    worker = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id,
        request,
        curator=worker.user_id,
        sound_engineer=worker.user_id,
    )

    # curator отсутствует → не меняется; sound_engineer=null → очищается
    response = await client.patch(
        f"/series/{series.id}/noactors",
        json={"sound_engineer": None},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["curator"]["user_id"] == worker.user_id
    assert data["sound_engineer"] is None


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_subtitler_maps_to_translator(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Поле subtitler в запросе соответствует полю translator в БД."""
    worker = await create_user(request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    # translator= — имя поля в модели Series
    series = await create_series(project.project_id, request, translator=worker.user_id)

    response = await client.patch(
        f"/series/{series.id}/noactors", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["subtitler"]["user_id"] == worker.user_id


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_noactors_unassigned_fields_are_null(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Поля без назначенного пользователя возвращаются как null."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)  # все поля = None

    response = await client.patch(
        f"/series/{series.id}/noactors", json={}, headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    for key in NOACTORS_KEYS:
        assert data[key] is None


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_invalid_state(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Значение state, не входящее в SeriesState, возвращает 422."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/data",
        json={"state": "несуществующий_статус"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "state",
    [s.value for s in SeriesState],
)
@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_update_series_data_all_valid_states(
    state: str,
    auth_headers: dict,
    client: AsyncClient,
    request: pytest.FixtureRequest,
):
    """Каждое допустимое значение SeriesState принимается без ошибок."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.patch(
        f"/series/{series.id}/data",
        json={"state": state},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == state


# ---------------------------------------------------------------------------
# POST /series/{seria_id}/materials
# ---------------------------------------------------------------------------

_TEST_FILE = ("material.txt", b"test material content", "text/plain")


async def test_create_material_no_auth(client: AsyncClient):
    response = await client.post(
        "/series/999999/materials",
        data={"material_title": "Тест"},
        files={"material_file": _TEST_FILE},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_material_series_not_found(auth_headers: dict, client: AsyncClient):
    response = await client.post(
        "/series/999999/materials",
        data={"material_title": "Тест"},
        files={"material_file": _TEST_FILE},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_create_material_forbidden_plain_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, не входящий в состав серии, получает 403."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.post(
        f"/series/{series.id}/materials",
        data={"material_title": "Тест"},
        files={"material_file": _TEST_FILE},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_material_ok_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор (уровень 2) успешно создаёт материал."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.post(
        f"/series/{series.id}/materials",
        data={"material_title": "Исходники"},
        files={"material_file": _TEST_FILE},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    request.addfinalizer(lambda: asyncio.run(_cleanup_material_file(data["material_link"])))

    assert data["material_title"] == "Исходники"
    assert data["material_link"].startswith("/team_files/")
    assert "id" in data


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_material_response_shape(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Ответ содержит ровно поля id, material_title, material_link."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.post(
        f"/series/{series.id}/materials",
        data={"material_title": "Тест"},
        files={"material_file": _TEST_FILE},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    request.addfinalizer(lambda: asyncio.run(_cleanup_material_file(data["material_link"])))

    assert set(data.keys()) == {"id", "material_title", "material_link"}


@pytest.mark.parametrize(
    "staff_field",
    ["curator", "sound_engineer", "raw_sound_engineer", "timer", "translator", "director"],
)
async def test_create_material_ok_as_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, назначенный на любую должность серии, может добавить материал."""
    staff_user, _ = await create_user_with_level(access_level=MEMBER_LEVEL, request=request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, **{staff_field: staff_user.user_id})
    headers = await login_user(client, staff_user.nickname)

    response = await client.post(
        f"/series/{series.id}/materials",
        data={"material_title": f"Материал через {staff_field}"},
        files={"material_file": _TEST_FILE},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    request.addfinalizer(lambda: asyncio.run(_cleanup_material_file(data["material_link"])))

    assert data["material_title"] == f"Материал через {staff_field}"


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_material_title_matches_param(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """material_title в ответе совпадает с переданным параметром."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    title = "Русская дорожка — финал"
    response = await client.post(
        f"/series/{series.id}/materials",
        data={"material_title": title},
        files={"material_file": _TEST_FILE},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    request.addfinalizer(lambda: asyncio.run(_cleanup_material_file(data["material_link"])))

    assert data["material_title"] == title


# ---------------------------------------------------------------------------
# DELETE /series/materials/{material_id}
# ---------------------------------------------------------------------------


async def test_delete_material_no_auth(client: AsyncClient):
    response = await client.delete("/series/materials/999999")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_material_not_found(auth_headers: dict, client: AsyncClient):
    response = await client.delete("/series/materials/999999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_delete_material_forbidden_plain_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, не входящий в состав серии, получает 403."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    material = await create_material(series.id, request)

    response = await client.delete(
        f"/series/materials/{material.id}", headers=auth_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_delete_material_ok_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор (уровень 2) успешно удаляет материал."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)
    material = await create_material(series.id, request)

    response = await client.delete(
        f"/series/materials/{material.id}", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "Материал успешно удалён"


@pytest.mark.parametrize(
    "staff_field",
    ["curator", "sound_engineer", "raw_sound_engineer", "timer", "translator", "director"],
)
async def test_delete_material_ok_as_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, назначенный на должность серии, может удалить материал."""
    staff_user, _ = await create_user_with_level(access_level=MEMBER_LEVEL, request=request)
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request, **{staff_field: staff_user.user_id})
    material = await create_material(series.id, request)
    headers = await login_user(client, staff_user.nickname)

    response = await client.delete(
        f"/series/materials/{material.id}", headers=headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "Материал успешно удалён"


# ---------------------------------------------------------------------------
# POST /series/{seria_id}/links
# ---------------------------------------------------------------------------


async def test_create_series_link_no_auth(client: AsyncClient):
    response = await client.post(
        "/series/999999/links",
        json={"link_url": "https://example.com", "link_title": "Тест"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_series_link_series_not_found(
    auth_headers: dict, client: AsyncClient
):
    response = await client.post(
        "/series/999999/links",
        json={"link_url": "https://example.com", "link_title": "Тест"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_create_series_link_forbidden_plain_member(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, не входящий в состав серии, получает 403."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.post(
        f"/series/{series.id}/links",
        json={"link_url": "https://example.com", "link_title": "Тест"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_series_link_ok_curator_level(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Куратор (уровень 2) успешно создаёт ссылку."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.post(
        f"/series/{series.id}/links",
        json={"link_url": "https://example.com/video", "link_title": "Видео"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    link_id = data["id"]
    request.addfinalizer(lambda: asyncio.run(_cleanup_series_link(link_id)))

    assert data["link_url"] == "https://example.com/video"
    assert data["link_title"] == "Видео"
    assert "id" in data


@pytest.mark.parametrize("auth_headers", [{"level": CURATOR_LEVEL}], indirect=True)
async def test_create_series_link_response_shape(
    auth_headers: dict, client: AsyncClient, request: pytest.FixtureRequest
):
    """Ответ содержит ровно поля id, link_url, link_title."""
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(project.project_id, request)

    response = await client.post(
        f"/series/{series.id}/links",
        json={"link_url": "https://example.com/shape", "link_title": "Форма"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    link_id = data["id"]
    request.addfinalizer(lambda: asyncio.run(_cleanup_series_link(link_id)))

    assert set(data.keys()) == {"id", "link_url", "link_title"}


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
async def test_create_series_link_ok_as_staff_member(
    staff_field: str, client: AsyncClient, request: pytest.FixtureRequest
):
    """Участник уровня 1, назначенный на любую должность серии, может добавить ссылку."""
    staff_user, _ = await create_user_with_level(
        access_level=MEMBER_LEVEL, request=request
    )
    other = await create_user(request)
    project = await create_project(curator_id=other.user_id, request=request)
    series = await create_series(
        project.project_id, request, **{staff_field: staff_user.user_id}
    )
    headers = await login_user(client, staff_user.nickname)

    response = await client.post(
        f"/series/{series.id}/links",
        json={
            "link_url": f"https://example.com/{staff_field}",
            "link_title": f"Ссылка через {staff_field}",
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    link_id = data["id"]
    request.addfinalizer(lambda: asyncio.run(_cleanup_series_link(link_id)))

    assert data["link_title"] == f"Ссылка через {staff_field}"

import pytest
from httpx import AsyncClient

from fastapi import status

from tests.helpers.users import create_user, create_user_with_level, login_user
from tests.helpers.projects import create_project
from tests.helpers.series import create_series, STAFF_WORK_TYPES
from tests.helpers.roles import create_role
from app.roles.models import RoleState
from app.series.models import SeriesState
from app.users.utils import MEMBER_LEVEL, CURATOR_LEVEL


@pytest.mark.parametrize("auth_headers", [{"level": MEMBER_LEVEL}], indirect=True)
async def test_work_existing_series_endpoint(auth_headers: dict, client: AsyncClient):
    response = await client.get("/series/", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "В данном проекте ещё нет серий."}


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

import asyncio

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select

from app.projects.models import ProjectRoleHistory
from app.series.models import Series
from tests.conftest import TestSession
from tests.helpers import _uid
from app.roles.models import Fix, Role, Record


async def post_role(
    client: AsyncClient,
    seria_id: int,
    role_name: str,
    headers: dict,
    request: pytest.FixtureRequest | None = None,
):
    """POST /series/{seria_id}/role. Registers DELETE cleanup when request is given."""
    response = await client.post(
        f"/series/{seria_id}/role",
        json={"role_name": role_name},
        headers=headers,
    )
    if request is not None and response.is_success:
        role_id = response.json()["id"]

        async def _delete() -> None:
            async with TestSession() as s:
                db_role = await s.get(Role, role_id)
                if db_role:
                    await s.delete(db_role)
                await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return response


async def create_role(
    series_id: int,
    user_id: int | None,
    request: pytest.FixtureRequest | None = None,
    **kwargs,
) -> Role:
    defaults = dict(
        role_name=f"role_{_uid()}",
        user_id=user_id,
        series_id=series_id,
        srt_url="",
    )
    defaults.update(kwargs)
    async with TestSession() as s:
        role = Role(**defaults)
        s.add(role)
        await s.commit()
        await s.refresh(role)

    if request is not None:
        role_id = role.role_id

        async def _delete() -> None:
            async with TestSession() as s:
                db_role = await s.get(Role, role_id)
                if db_role:
                    await s.delete(db_role)
                await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return role


async def put_role_actor(
    client: AsyncClient,
    role_id: int,
    actor_id: int | None,
    headers: dict,
    request: pytest.FixtureRequest | None = None,
) -> Response:
    result = await client.put(
        f"/series/role/{role_id}/actor",
        json={"actor_id": actor_id},
        headers=headers,
    )

    if not result.is_success or request is None:
        return result

    async def _delete_history() -> None:
        async with TestSession() as s:
            role = await s.get(Role, role_id)
            if role is None:
                return

            series = await s.get(Series, role.series_id)
            if series is None:
                return

            history = await s.scalar(
                select(ProjectRoleHistory).where(
                    ProjectRoleHistory.project_id == series.project_id,
                    ProjectRoleHistory.role_title.ilike(role.role_name),
                )
            )
            if history:
                await s.delete(history)
                await s.commit()

    request.addfinalizer(lambda: asyncio.run(_delete_history()))

    return result


async def patch_role_state(
    client: AsyncClient,
    role_id: int,
    headers: dict,
    **kwargs,
) -> Response:
    """PATCH /series/role/{role_id}/state with optional checked= and/or timed= kwargs."""
    return await client.patch(
        f"/series/role/{role_id}/state",
        json=kwargs,
        headers=headers,
    )


async def put_role_subtitle(
    client: AsyncClient,
    role_id: int,
    headers: dict,
    filename: str = "test.srt",
    content: bytes = b"1\n00:00:01,000 --> 00:00:02,000\nHello\n",
    request: pytest.FixtureRequest | None = None,
) -> Response:
    """PUT /series/role/{role_id}/subtitle. Registers Fix cleanup when request is given."""
    response = await client.put(
        f"/series/role/{role_id}/subtitle",
        files={"srt_file": (filename, content, "text/plain")},
        headers=headers,
    )
    if request is not None and response.is_success:
        fix_id = response.json()["fixes"][-1]["id"]

        async def _delete_fix() -> None:
            async with TestSession() as s:
                db_fix = await s.get(Fix, fix_id)
                if db_fix:
                    await s.delete(db_fix)
                    await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete_fix()))

    return response


async def post_role_record(
    client: AsyncClient,
    role_id: int,
    headers: dict,
    record_title: str = "test.wav",
    record_note: str | None = None,
    content: bytes = b"RIFF\x00\x00\x00\x00WAVEfmt ",
    request: pytest.FixtureRequest | None = None,
) -> Response:
    """POST /series/role/{role_id}/records. Registers Record cleanup when request is given."""
    response = await client.post(
        f"/series/role/{role_id}/records",
        data=(
            {"record_title": record_title, "note": record_note}
            if record_note is not None
            else {"record_title": record_title}
        ),
        files={"record_file": (record_title, content, "audio/wav")},
        headers=headers,
    )
    if request is not None and response.is_success:
        record_id = response.json()["record"]["id"]

        async def _delete() -> None:
            async with TestSession() as s:
                db_record = await s.get(Record, record_id)
                if db_record:
                    await s.delete(db_record)
                    await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return response


async def create_record(
    role_id: int,
    request: pytest.FixtureRequest | None = None,
    record_url: str | None = None,
    record_prev_title: str | None = None,
) -> Record:
    """Create a Record for a role directly in the test DB."""
    async with TestSession() as s:
        record = Record(
            role_id=role_id,
            record_url=record_url or f"/media/{_uid()}.wav",
            record_prev_title=record_prev_title or f"{_uid()}.wav",
        )
        s.add(record)
        await s.commit()
        await s.refresh(record)

    if request is not None:
        record_id = record.id

        async def _delete() -> None:
            async with TestSession() as s:
                db_record = await s.get(Record, record_id)
                if db_record:
                    await s.delete(db_record)
                    await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return record


async def delete_record(
    client: AsyncClient,
    record_id: int,
    headers: dict,
) -> Response:
    return await client.delete(
        f"/series/role/records/{record_id}",
        headers=headers,
    )


async def patch_role_note(
    client: AsyncClient,
    role_id: int,
    note: str,
    headers: dict,
) -> Response:
    """PATCH /series/role/{role_id}/note."""
    return await client.patch(
        f"/series/role/{role_id}/note",
        json={"note": note},
        headers=headers,
    )


async def delete_role_fix(
    client: AsyncClient,
    fix_id: int,
    headers: dict,
) -> Response:
    """DELETE /series/role/fixs/{fix_id}."""
    return await client.delete(
        f"/series/role/fixs/{fix_id}",
        headers=headers,
    )


async def create_fix(
    role_id: int,
    phrase: int = 1,
    note: str = "тестовый фикс",
    request: pytest.FixtureRequest | None = None,
) -> Fix:
    """Create a Fix for a role directly in the test DB."""
    async with TestSession() as s:
        fix = Fix(role_id=role_id, phrase=phrase, note=note, ready=False)
        s.add(fix)
        await s.commit()
        await s.refresh(fix)

    if request is not None:
        fix_id = fix.id

        async def _delete() -> None:
            async with TestSession() as s:
                db_fix = await s.get(Fix, fix_id)
                if db_fix:
                    await s.delete(db_fix)
                    await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return fix


async def post_role_fix(
    client: AsyncClient,
    role_id: int,
    phrase: int,
    note: str,
    headers: dict,
    request: pytest.FixtureRequest | None = None,
) -> Response:
    """POST /series/role/{role_id}/fixs. Registers Fix cleanup when request is given."""
    response = await client.post(
        f"/series/role/{role_id}/fixs",
        json={"phrase": phrase, "note": note},
        headers=headers,
    )
    if request is not None and response.is_success:
        fix_id = response.json()["fix"]["id"]

        async def _delete() -> None:
            async with TestSession() as s:
                db_fix = await s.get(Fix, fix_id)
                if db_fix:
                    await s.delete(db_fix)
                    await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return response

import asyncio
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from app.database import async_session_maker
from app.series.models import AssFile
from app.series.utils import MEDIA_ROOT


def cleanup_response_files(response_json: dict) -> None:
    """Удаляет ASS и SRT файлы, созданные эндпоинтом PUT /{seria_id}/subs."""
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


async def _delete_ass_fix(fix_id: int) -> None:
    from tests.conftest import TestSession

    async with TestSession() as s:
        db_fix = await s.get(AssFile, fix_id)
        if db_fix:
            await s.delete(db_fix)
        await s.commit()


async def subs_fix_post(
    client: AsyncClient,
    seria_id: int,
    fix_note: str,
    headers: dict,
    request: pytest.FixtureRequest | None = None,
) -> httpx.Response:
    """
    Отправляет POST /series/{seria_id}/subs/fix.

    Если передан request и ответ успешный (2xx), автоматически регистрирует
    через addfinalizer удаление созданной AssFile-записи.
    """
    response = await client.post(
        f"/series/{seria_id}/subs/fix",
        json={"fix_note": fix_note},
        headers=headers,
    )
    if request is not None and response.is_success:
        fix_id = response.json()["fix_id"]
        request.addfinalizer(lambda: asyncio.run(_delete_ass_fix(fix_id)))
    return response


async def subs_fix_delete(
    client: AsyncClient,
    fix_id: int,
    headers: dict,
) -> httpx.Response:
    """Отправляет DELETE /series/subs/fix/{fix_id}."""
    return await client.delete(f"/series/subs/fix/{fix_id}", headers=headers)


async def subs_put(
    client: AsyncClient,
    seria_id: int,
    ass_path: Path,
    parse_type: str,
    headers: dict,
    request: pytest.FixtureRequest | None = None,
) -> httpx.Response:
    """
    Отправляет PUT /series/{seria_id}/subs с указанным ASS-файлом.

    Если передан request и ответ успешный (2xx), автоматически регистрирует
    через addfinalizer удаление ASS/SRT файлов, созданных эндпоинтом.
    """
    with ass_path.open("rb") as f:
        response = await client.put(
            f"/series/{seria_id}/subs",
            data={"parse_type": parse_type},
            files={"ass_file": (ass_path.name, f, "text/plain")},
            headers=headers,
        )
    if request is not None and response.is_success:
        data = response.json()
        request.addfinalizer(lambda: cleanup_response_files(data))
    return response

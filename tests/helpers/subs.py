from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

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

import asyncio
from datetime import date

import pytest

from tests.conftest import TestSession
from tests.helpers import _uid
from app.series.models import Series, SeriesState, Material


STAFF_WORK_TYPES = {
    "куратор",
    "звукорежиссёр",
    "звукорежиссёр минусовки",
    "режиссёр",
    "таймер",
    "саббер",
}


async def create_series(
    project_id: int,
    request: pytest.FixtureRequest | None = None,
    **kwargs,
) -> Series:
    today = date.today()
    defaults = dict(
        title=f"series_{_uid()}",
        project_id=project_id,
        start_date=today,
        first_deadline=today,
        second_deadline=today,
        exp_publish_date=today,
        state=SeriesState.VOICE_OVER,
    )
    defaults.update(kwargs)
    async with TestSession() as s:
        series = Series(**defaults)
        s.add(series)
        await s.commit()
        await s.refresh(series)

    if request is not None:
        series_id = series.id

        async def _delete() -> None:
            async with TestSession() as s:
                db_series = await s.get(Series, series_id)
                if db_series:
                    await s.delete(db_series)
                await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return series


async def create_material(
    series_id: int,
    request: pytest.FixtureRequest | None = None,
    title: str = "Тестовый материал",
) -> Material:
    async with TestSession() as s:
        material = Material(
            series_id=series_id,
            material_title=title,
            material_prev_title=f"{_uid()}.txt",
            material_link=f"/team_files/{_uid()}.txt",
        )
        s.add(material)
        await s.commit()
        await s.refresh(material)

    if request is not None:
        material_id = material.id

        async def _delete() -> None:
            async with TestSession() as s:
                db_material = await s.get(Material, material_id)
                if db_material:
                    await s.delete(db_material)
                    await s.commit()

        request.addfinalizer(lambda: asyncio.run(_delete()))

    return material

from datetime import date

from tests.conftest import TestSession
from tests.helpers import _uid
from app.series.models import Series, SeriesState


STAFF_WORK_TYPES = {
    "куратор",
    "звукорежиссёр",
    "звукорежиссёр минусовки",
    "режиссёр",
    "таймер",
    "саббер",
}


async def create_series(project_id: int, **kwargs) -> Series:
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
        return series

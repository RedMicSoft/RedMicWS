from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.users.models import User

from .schemas import SeriesParticipant
from .models import Series
from ..roles.models import Role

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media"


async def save_srt(srt: UploadFile) -> str:
    if not srt.filename.lower().endswith(".srt"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл должен быть .srt")

    content = await srt.read()
    file_path = MEDIA_ROOT / "srt" / srt.filename
    file_path.write_bytes(content)

    return f"/media/srt/{srt.filename}"


def get_series_no_actors(series: Series) -> dict:
    no_actors = {}
    for staff_title in series.staff_titles:
        no_actors[staff_title] = series.__dict__[staff_title]
    return no_actors


async def get_series_participants(series: Series, db: AsyncSession):
    participants = [role.user for role in series.roles]
    staff = await db.scalars(select(User).where(User.user_id.in_(series.staff_ids)))
    participants.extend(staff.all())
    res = []
    for participant in participants:
        if participant is None:
            continue
        res.append(
            SeriesParticipant(
                id=participant.user_id,
                nickname=participant.nickname,
                avatar_url=participant.avatar_url,
            )
        )
    return res


# функция для расчета состояния серия(dub_progress) согласно диздоку. дай бог она работает))
def compute_dub_progress(roles: list[Role]):
    if not roles:
        return "no_roles"
    users_rests = []
    finished_roles = []
    for role in roles:
        if not role.user_id:
            return "no_roles"
        if (
            role.checked
            and role.timed
            and len(role.fixes) == 0
            and len(role.records) >= 1
        ):
            finished_roles.append(True)
        else:
            if role.user.is_active == False:
                users_rests.append(role.user.user_id)
            finished_roles.append(False)

    if users_rests:
        return "on_rest"

    if all(finished_roles):
        return "finished"
    else:
        return "on_process"

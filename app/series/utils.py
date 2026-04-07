from typing import cast

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.projects.models import Project as ProjectModel
from app.projects.utils import AccessChecker
from app.users.models import User as UserModel
from app.users.utils import get_current_user, get_max_lvl, CURATOR_LEVEL

from .schemas import SeriesParticipant
from .models import Series, Material, SeriesLink
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
    participants = [cast(UserModel, cast(Role, role).user) for role in series.roles]
    staff = await db.scalars(
        select(UserModel).where(UserModel.user_id.in_(series.staff_ids))
    )
    participants.extend(staff.all())
    res = []
    for participant in participants:
        if participant is None:
            continue
        res.append(
            SeriesParticipant(
                user_id=participant.user_id,
                nickname=participant.nickname,
                avatar_url=participant.avatar_url,
                is_active=participant.is_active,
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


class SeriesChecker:
    async def __call__(
        self, seria_id: int, db: AsyncSession = Depends(get_db)
    ) -> Series:
        db_seria = await db.get(Series, seria_id)
        if not db_seria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
            )
        return db_seria


class SeriesAccessChecker:
    async def __call__(
        self,
        user: UserModel = Depends(get_current_user),
        db_seria: Series = Depends(SeriesChecker()),
        db: AsyncSession = Depends(get_db),
    ) -> Series:
        db_project = await db.get(ProjectModel, db_seria.project_id)
        if not db_project:
            raise HTTPException(status_code=404, detail="Проект не найден.")

        await AccessChecker()(user=user, db_project=db_project, db=db)
        return db_seria


class SeriesNoActorsAccessChecker:
    async def __call__(
        self,
        user: UserModel = Depends(get_current_user),
        db_seria: Series = Depends(SeriesChecker()),
        db: AsyncSession = Depends(get_db),
    ) -> Series:
        project_curator_id = None
        db_project = await db.get(ProjectModel, db_seria.project_id)
        if db_project:
            project_curator_id = db_project.curator_id

        try:
            user_level = await get_max_lvl(db, user)
        except HTTPException:
            user_level = 0

        if (
            user_level < CURATOR_LEVEL
            and user.user_id != db_seria.curator
            and user.user_id != project_curator_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Запрещено."
            )

        return db_seria


class SeriesDataAccessChecker:
    async def __call__(
        self,
        user: UserModel = Depends(get_current_user),
        db_seria: Series = Depends(SeriesChecker()),
        db: AsyncSession = Depends(get_db),
    ) -> Series:
        try:
            user_level = await get_max_lvl(db, user)
        except HTTPException:
            user_level = 0

        if user_level < CURATOR_LEVEL and user.user_id not in db_seria.staff_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Запрещено."
            )
        return db_seria


class LinkChecker:
    async def __call__(
        self, link_id: int, db: AsyncSession = Depends(get_db)
    ) -> SeriesLink:
        db_link = await db.get(SeriesLink, link_id)
        if not db_link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ссылка не найдена."
            )
        return db_link


class LinkAccessChecker:
    async def __call__(
        self,
        user: UserModel = Depends(get_current_user),
        db_link: SeriesLink = Depends(LinkChecker()),
        db: AsyncSession = Depends(get_db),
    ) -> SeriesLink:
        db_seria = await db.get(Series, db_link.series_id)
        if not db_seria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
            )

        await SeriesDataAccessChecker()(user=user, db_seria=db_seria, db=db)

        return db_link


class MaterialChecker:
    async def __call__(
        self, material_id: int, db: AsyncSession = Depends(get_db)
    ) -> Material:
        db_material = await db.get(Material, material_id)
        if not db_material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден."
            )
        return db_material


class MaterialAccessChecker:
    async def __call__(
        self,
        user: UserModel = Depends(get_current_user),
        db_material: Material = Depends(MaterialChecker()),
        db: AsyncSession = Depends(get_db),
    ) -> Material:
        try:
            user_level = await get_max_lvl(db, user)
        except HTTPException:
            user_level = 0

        db_seria = await db.get(Series, db_material.series_id)
        if not db_seria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
            )

        await SeriesDataAccessChecker()(user=user, db_seria=db_seria, db=db)

        if user_level < CURATOR_LEVEL and user.user_id not in db_seria.staff_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Запрещено."
            )
        return db_material

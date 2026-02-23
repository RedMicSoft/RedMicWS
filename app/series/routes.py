from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.series.schemas import SeriesResponse, SeriesCreate
from app.users.utils import get_current_user
from app.roles.schemas import RoleCreate
from ..users import get_max_lvl
from ..users.models import User as UserModel
from .utils import save_srt
from .models import Series
from app.projects.models import Project as ProjectModel

router = APIRouter(prefix="/series", tags=["series"])


@router.get("/", response_model=list[SeriesResponse])
async def get_series(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    db_project = await db.get(ProjectModel, project_id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден."
        )

    db_series = await db.scalars(select(Series).where(Series.project_id == project_id))

    return db_series


@router.post("/")
async def create_series(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 2:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Запрещено.")

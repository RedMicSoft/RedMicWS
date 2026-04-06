from datetime import date, timedelta
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    status,
    Depends,
    Query,
)
from sqlalchemy import select, null, union_all, literal, case, false, true, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.series.schemas import (
    SeriesListResponse,
    SeriesCreate,
    SeriesCreateProjectResponse,
    SeriesCreateSeriesResponse,
    SeriesParticipant,
    UserWorkItem,
    UserWorkSeriaInfo,
    UserWorkProjectInfo,
    UserWorkRoleInfo,
)
from app.users.utils import UserChecker, get_current_user
from app.roles.schemas import RoleCreate
from ..projects.utils import ProjectChecker, AccessChecker
from ..users import get_max_lvl
from ..users.models import User as UserModel
from .utils import (
    save_srt,
    compute_dub_progress,
    get_series_participants,
    get_series_no_actors,
    SeriesAccessChecker,
)
from .models import Series
from app.projects.models import Project as ProjectModel
from app.roles.models import Role, RoleState


router = APIRouter(prefix="/series", tags=["series"])

STAFF_FIELD_TO_WORK_TYPE = {
    "curator": "куратор",
    "sound_engineer": "звукорежиссёр",
    "raw_sound_engineer": "звукорежиссёр минусовки",
    "director": "режиссёр",
    "timer": "таймер",
    "translator": "саббер",
}


@router.get("/user/{user_id}/work", response_model=list[UserWorkItem])
async def get_user_work(
    user: Annotated[UserModel, Depends(UserChecker())],
    db: AsyncSession = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    staff_subqueries = [
        select(
            Series.id.label("seria_id"),
            Series.title.label("seria_title"),
            Series.state.label("seria_state"),
            Series.ass_url.label("ass_url"),
            ProjectModel.project_id.label("project_id"),
            ProjectModel.title.label("project_title"),
            literal(work_type).label("work_type"),
            false().label("role_is_ready"),
            literal(None, type_=String).label("role_name"),
            literal(None, type_=String).label("role_state"),
        )
        .join(ProjectModel, Series.project_id == ProjectModel.project_id)
        .where(getattr(Series, field) == user.user_id)
        for field, work_type in STAFF_FIELD_TO_WORK_TYPE.items()
    ]

    actor_subquery = (
        select(
            Series.id.label("seria_id"),
            Series.title.label("seria_title"),
            Series.state.label("seria_state"),
            Series.ass_url.label("ass_url"),
            ProjectModel.project_id.label("project_id"),
            ProjectModel.title.label("project_title"),
            literal("актёр").label("work_type"),
            case((Role.state == RoleState.MIXING_READY, true()), else_=false()).label(
                "role_is_ready"
            ),
            Role.role_name.label("role_name"),
            Role.state.label("role_state"),
        )
        .join(Series, Role.series_id == Series.id)
        .join(ProjectModel, Series.project_id == ProjectModel.project_id)
        .where(Role.user_id == user.user_id)
    )

    rows = (await db.execute(union_all(*staff_subqueries, actor_subquery))).all()

    return [
        UserWorkItem(
            seria=UserWorkSeriaInfo(
                seria_id=r.seria_id,
                seria_title=r.seria_title,
                state=r.seria_state,
            ),
            project=UserWorkProjectInfo(
                project_id=r.project_id,
                project_title=r.project_title,
            ),
            work_type=r.work_type,
            role_is_ready=bool(r.role_is_ready),
            subs=r.ass_url is not None,
            role=UserWorkRoleInfo(role_name=r.role_name, state=r.role_state)
            if r.role_name is not None
            else None,
        )
        for r in rows
    ]


@router.get("/", response_model=list[SeriesListResponse])
async def get_series(
    project_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    db_series = select(Series)

    if project_id:
        project_checker = ProjectChecker()
        db_project = project_checker(project_id, db)
        db_series = db_series.where(Series.project_id == project_id)

    db_series = db_series.options(
        selectinload(Series.roles).selectinload(Role.user),
        selectinload(Series.roles).selectinload(Role.fixes),
        selectinload(Series.roles).selectinload(Role.records),
    )
    db_series = await db.scalars(db_series)
    db_series = db_series.all()
    if not db_series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="В данном проекте ещё нет серий.",
        )

    return [
        {
            "id": s.id,
            "project_id": s.project_id,
            "title": s.title,
            "state": s.state,
            "dub_progress": compute_dub_progress(s.roles),
            "participants": await get_series_participants(s, db),
        }
        for s in db_series
    ]


@router.post("/{project_id}", response_model=SeriesCreateSeriesResponse)
async def create_series(
    project_id: int,
    seria: SeriesCreate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
    db_project: ProjectModel = Depends(ProjectChecker()),
    is_access=Depends(AccessChecker()),
):
    curator = await db.get(UserModel, db_project.curator_id)
    start_date = date.today()
    first_deadline = start_date + timedelta(days=seria.stage_time)
    second_deadline = first_deadline + timedelta(days=seria.stage_time)
    exp_publish_date = second_deadline + timedelta(days=1)
    db_seria = Series(
        title=seria.title,
        project_id=project_id,
        curator=db_project.curator_id,
        sound_engineer=null(),
        raw_sound_engineer=null(),
        timer=null(),
        translator=null(),
        director=null(),
        start_date=start_date,
        first_deadline=first_deadline,
        second_deadline=second_deadline,
        exp_publish_date=exp_publish_date,
    )
    db.add(db_seria)
    await db.commit()

    db_seria = await db.scalar(
        select(Series)
        .where(Series.id == db_seria.id)
        .options(
            selectinload(Series.materials),
            selectinload(Series.links),
            selectinload(Series.roles),
        )
    )
    db_seria.no_actors = get_series_no_actors(db_seria)
    db_seria.no_actors["curator"] = SeriesParticipant.model_validate(curator)

    series_date = SeriesCreateSeriesResponse.model_validate(db_seria).model_dump()

    series_date["project"] = SeriesCreateProjectResponse.model_validate(db_project)

    series_response = SeriesCreateSeriesResponse(**series_date)

    return series_response


@router.get("/{series_id}")
async def get_series_by_id(
    series_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db_series = await db.scalar(select(Series).where(Series.id == series_id))
    if not db_series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
        )

    db_series = await db.scalar()


@router.delete("/{seria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesAccessChecker())],
):
    await db.delete(db_seria)
    await db.commit()

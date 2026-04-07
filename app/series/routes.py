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
from sqlalchemy import select, null, union_all, literal, false, String, cast
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
    SeriesDataUpdate,
    SeriesDataResponse,
    SeriesNoActorsUpdate,
    SeriesNoActorsResponse,
    MaterialCreateResponse,
    SeriesLinkCreate,
    SeriesLinkResponse,
)
from app.users.utils import UserChecker, get_current_user, CURATOR_LEVEL
from app.roles.schemas import RoleCreate
from ..projects.utils import ProjectChecker, AccessChecker
from ..users import get_max_lvl
from ..users.models import User as UserModel
from .utils import (
    MaterialAccessChecker,
    save_srt,
    compute_dub_progress,
    get_series_participants,
    get_series_no_actors,
    SeriesAccessChecker,
    SeriesDataAccessChecker,
    SeriesNoActorsAccessChecker,
)
from .models import Series, Material, SeriesLink
from app.projects.models import Project as ProjectModel
from app.roles.models import Role, RoleState
from app.files.models import FileModel
from app.files.utils import save_file


router = APIRouter(prefix="/series", tags=["series"])

STAFF_FIELD_TO_WORK_TYPE = {
    "curator": "куратор",
    "sound_engineer": "звукорежиссёр",
    "raw_sound_engineer": "звукорежиссёр минусовки",
    "director": "режиссёр",
    "timer": "таймер",
    "translator": "саббер",
}


@router.get(
    "/user/{user_id}/work",
    response_model=list[UserWorkItem],
    dependencies=[Depends(get_current_user)],
)
async def get_user_work(
    user: Annotated[UserModel, Depends(UserChecker())],
    db: AsyncSession = Depends(get_db),
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
            (Role.state == RoleState.MIXING_READY).label("role_is_ready"),
            Role.role_name.label("role_name"),
            cast(Role.state, String).label("role_state"),
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


@router.patch("/{seria_id}/noactors", response_model=SeriesNoActorsResponse)
async def update_series_no_actors(
    data: SeriesNoActorsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesNoActorsAccessChecker())],
):
    request_to_model = {
        "curator": "curator",
        "sound_engineer": "sound_engineer",
        "raw_sound_engineer": "raw_sound_engineer",
        "director": "director",
        "timer": "timer",
        "subtitler": "translator",
    }

    for request_field, model_field in request_to_model.items():
        if request_field in data.model_fields_set:
            setattr(db_seria, model_field, getattr(data, request_field))

    await db.commit()
    await db.refresh(db_seria)

    field_map = {
        "curator": db_seria.curator,
        "sound_engineer": db_seria.sound_engineer,
        "raw_sound_engineer": db_seria.raw_sound_engineer,
        "director": db_seria.director,
        "timer": db_seria.timer,
        "subtitler": db_seria.translator,
    }

    user_ids = {uid for uid in field_map.values() if uid is not None}
    users: dict[int, UserModel] = {}
    if user_ids:
        result = await db.scalars(
            select(UserModel).where(UserModel.user_id.in_(user_ids))
        )
        for u in result.all():
            users[u.user_id] = u

    return SeriesNoActorsResponse(
        **{
            field: (
                SeriesParticipant(
                    user_id=u.user_id,
                    nickname=u.nickname,
                    avatar_url=u.avatar_url,
                    is_active=u.is_active,
                )
                if uid is not None and (u := users.get(uid)) is not None
                else None
            )
            for field, uid in field_map.items()
        }
    )


@router.patch("/{seria_id}/data", response_model=SeriesDataResponse)
async def update_series_data(
    data: SeriesDataUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesDataAccessChecker())],
):
    if data.seria_title is not None:
        db_seria.title = data.seria_title
    if data.start_date is not None:
        db_seria.start_date = data.start_date
    if data.first_stage_date is not None:
        db_seria.first_deadline = data.first_stage_date
    if data.second_stage_date is not None:
        db_seria.second_deadline = data.second_stage_date
    if data.publication_date is not None:
        db_seria.exp_publish_date = data.publication_date
    if data.note is not None:
        db_seria.note = data.note
    if data.state is not None:
        db_seria.state = data.state

    await db.commit()
    await db.refresh(db_seria)

    return SeriesDataResponse(
        seria_title=db_seria.title,
        start_date=db_seria.start_date,
        first_stage_date=db_seria.first_deadline,
        second_stage_date=db_seria.second_deadline,
        publication_date=db_seria.exp_publish_date,
        note=db_seria.note,
        state=db_seria.state,
    )


@router.post(
    "/{seria_id}/materials",
    response_model=MaterialCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_material(
    material_file: UploadFile,
    material_title: Annotated[str, Form()],
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesDataAccessChecker())],
) -> Material:
    saved = await save_file(material_file)

    db_file = FileModel(
        filename=material_title,
        file_url=saved["file_url"],
        category="material",
        prev_filename=saved["prev_filename"],
    )
    db.add(db_file)

    db_material = Material(
        series_id=db_seria.id,
        material_title=material_title,
        material_prev_title=saved["prev_filename"],
        material_link=saved["file_url"],
    )
    db.add(db_material)

    await db.commit()
    await db.refresh(db_material)

    return db_material


@router.post(
    "/{seria_id}/links",
    response_model=SeriesLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_series_link(
    data: SeriesLinkCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesDataAccessChecker())],
) -> SeriesLink:
    db_link = SeriesLink(
        series_id=db_seria.id,
        link_url=data.link_url,
        link_title=data.link_title,
    )
    db.add(db_link)
    await db.commit()
    await db.refresh(db_link)
    return db_link


@router.delete(
    "/materials/{material_id}",
    response_model=str,
    dependencies=[Depends(get_current_user)],
)
async def delete_material(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_material: Annotated[Material, Depends(MaterialAccessChecker())],
) -> str:
    await db.delete(db_material)
    await db.commit()

    return "Материал успешно удалён"


@router.delete("/{seria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesAccessChecker())],
):
    await db.delete(db_seria)
    await db.commit()

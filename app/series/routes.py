from datetime import date, datetime, timedelta
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
    SubsUpdateResponse,
    AssFileSubsResponse,
    AssFixItemResponse,
    AssFixCreateRequest,
    AssFixCreateResponse,
    RoleSubsResponse,
    ActorSubsResponse,
    FixSubsResponse,
    RecordSubsResponse,
    RoleCreateRequest,
    RoleCreateResponse,
    ActorCreateResponse,
    RoleActorUpdate,
    RoleActorResponse,
    RoleStateUpdate,
    RoleStateResponse,
    RoleSubtitleFixResponse,
    RoleSubtitleResponse,
    RecordItemResponse,
    RecordAddResponse,
    RecordDeleteResponse,
    RoleNoteUpdate,
    RoleNoteResponse,
)
from app.users.utils import UserChecker, get_current_user, CURATOR_LEVEL
from app.roles.schemas import RoleCreate
from ..projects.utils import ProjectChecker, AccessChecker
from ..users.models import User as UserModel
from .utils import (
    MaterialAccessChecker,
    LinkAccessChecker,
    delete_role_srt,
    delete_series_subs,
    generate_srt_filename,
    save_srt,
    save_ass,
    compute_dub_progress,
    compute_role_state,
    get_series_participants,
    get_series_no_actors,
    SeriesAccessChecker,
    SeriesDataAccessChecker,
    SeriesNoActorsAccessChecker,
    SeriesRoleCreateAccessChecker,
    SeriesRoleDeleteAccessChecker,
    SeriesRoleActorSetAccessChecker,
    SeriesRoleStateAccessChecker,
    SeriesRoleSubtitleAccessChecker,
    SeriesRoleRecordAccessChecker,
    SeriesRoleRecordDeleteAccessChecker,
    SubsAccessChecker,
    AssFixAccessChecker,
    BASE_DIR,
    SUBS_ROOT,
    save_srt_content,
    save_record,
)
from .models import Series, Material, SeriesLink, AssFile
from app.projects.models import Project as ProjectModel, ProjectRoleHistory
from app.roles.models import Role, RoleState, Fix, Record
from app.files.utils import save_file
from .parser import ASSParser


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
            role=(
                UserWorkRoleInfo(role_name=r.role_name, state=r.role_state)
                if r.role_name is not None
                else None
            ),
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
    query = (
        select(Series)
        .where(Series.id == series_id)
        .options(
            selectinload(Series.project),
            selectinload(Series.materials),
            selectinload(Series.links),
            selectinload(Series.roles).selectinload(Role.user),
            selectinload(Series.roles).selectinload(Role.fixes),
            selectinload(Series.roles).selectinload(Role.records),
        )
    )

    result = await db.execute(query)
    s = result.scalar_one_or_none()

    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
        )

    # Собираем ID персонала, исключая заглушку -1
    valid_staff_ids = [uid for uid in s.staff_ids if uid is not None and uid != -1]

    staff_map = {}
    if valid_staff_ids:
        staff_users = await db.execute(
            select(UserModel).where(UserModel.user_id.in_(valid_staff_ids))
        )
        staff_map = {u.user_id: u for u in staff_users.scalars().all()}

    def format_user(user_id):
        if user_id is None or user_id == -1:
            return None
        u = staff_map.get(user_id)
        if not u:
            return None
        return {
            "user_id": u.user_id,
            "nickname": u.nickname,
            "avatar_url": u.avatar_url,
            "is_active": u.is_active,
        }

    def format_date(d: date):
        return d.strftime("%d.%m.%y") if d else None

    def get_role_state(role):
        # Используем безопасный доступ к атрибутам, так как они могут быть не в модели
        records = getattr(role, "records", [])
        fixes = getattr(role, "fixes", [])
        if not records:
            return "не загружена"
        if not getattr(role, "timed", True):
            return "не затаймлена"
        if not getattr(role, "checked", True):
            return "не проверена"
        if fixes and any(not getattr(f, "ready", False) for f in fixes):
            return "требуются фиксы"
        return "готова к сведению"

    return {
        "id": s.id,
        "project": {
            "project_id": s.project.project_id,
            "project_title": s.project.title,
            "project_curator_id": getattr(s.project, "curator_id", None),
            "project_image_url": getattr(s.project, "image_url", None),
        },
        "seria_title": s.title,
        "start_date": format_date(s.start_date),
        "first_stage_date": format_date(s.first_deadline),
        "second_stage_date": format_date(s.second_deadline),
        "publication_date": format_date(s.exp_publish_date),
        "note": s.note,
        "state": s.state.value if hasattr(s.state, "value") else s.state,
        "materials": [
            {
                "id": m.id,
                "material_title": m.material_title,
                "material_link": m.material_link,
            }
            for m in s.materials
        ],
        "ass_file": {"ass_file_url": s.ass_url, "ass_fixes": []}, # Можно добавить логику загрузки AssFile если нужно
        "links": [
            {"id": l.id, "link_title": l.link_title, "link_url": l.link_url}
            for l in s.links
        ],
        "no_actors": {
            "curator": format_user(s.curator),
            "sound_engineer": format_user(s.sound_engineer),
            "raw_sound_engineer": format_user(s.raw_sound_engineer),
            "director": format_user(s.director),
            "timer": format_user(s.timer),
            "subtitler": format_user(s.translator),
        },
        "roles": [
            {
                "id": getattr(r, "id", getattr(r, "role_id", None)),
                "role_name": r.role_name,
                "actor": {
                    "user_id": r.user.user_id if r.user else None,
                    "nickname": r.user.nickname if r.user else "Не назначен",
                    "avatar_url": r.user.avatar_url if r.user else None,
                    "is_active": r.user.is_active if r.user else False,
                },
                "fixes": [
                    {
                        "id": f.id,
                        "phrase": getattr(f, "phrase", getattr(f, "phrase_number", 0)),
                        "note": f.note,
                        "ready": f.ready,
                    }
                    for f in r.fixes
                ],
                "note": getattr(r, "note", ""),
                "checked": getattr(r, "checked", False),
                "timed": getattr(r, "timed", False),
                "state": get_role_state(r),
                "subtitle": getattr(r, "srt_url", None),
                "records": [
                    {
                        "id": rec.id,
                        "record_title": getattr(rec, "title", "Без названия"),
                        "record_note": getattr(rec, "analysis", ""),
                        "record_url": getattr(rec, "url", ""),
                    }
                    for rec in r.records
                ],
            }
            for r in s.roles
        ],
    }


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

    incoming_user_ids = {
        getattr(data, field)
        for field in request_to_model
        if field in data.model_fields_set and getattr(data, field) is not None
    }
    if incoming_user_ids:
        existing_ids = set(
            await db.scalars(
                select(UserModel.user_id).where(
                    UserModel.user_id.in_(incoming_user_ids)
                )
            )
        )
        missing = incoming_user_ids - existing_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователи не найдены: {sorted(missing)}",
            )

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
    "/links/{link_id}",
    response_model=str,
    dependencies=[Depends(get_current_user)],
)
async def delete_series_link(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_link: Annotated[SeriesLink, Depends(LinkAccessChecker())],
) -> str:
    await db.delete(db_link)
    await db.commit()

    return "Ссылка успешно удалена"


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


@router.put("/{seria_id}/subs", response_model=SubsUpdateResponse)
async def update_series_subs(
    seria_id: int,
    parse_type: Annotated[str, Form()],
    ass_file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Series, Depends(SubsAccessChecker())],
) -> SubsUpdateResponse:
    """
    Загружает/обновляет ASS-файл серии, парсит роли и создаёт/обновляет их.
    parse_type: "name" — роли из поля Name, "style" — из поля Style.
    """
    db_seria = await db.scalar(
        select(Series)
        .where(Series.id == seria_id)
        .options(
            selectinload(Series.project).selectinload(ProjectModel.roles),
            selectinload(Series.roles).selectinload(Role.user),
            selectinload(Series.roles).selectinload(Role.fixes),
            selectinload(Series.roles).selectinload(Role.records),
        )
    )

    if db_seria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
        )

    had_subs = db_seria.ass_url is not None
    ass_url = await save_ass(
        ass_file, seria_id, db_seria.project.title, db_seria.title
    )
    db_seria.ass_url = ass_url

    ass_full_path = BASE_DIR / ass_url.lstrip("/")
    use_name = parse_type.lower() != "style"
    parser = ASSParser(filename=str(ass_full_path), use_name=use_name)
    parser.load()

    project_roles_lookup: dict[str, int] = {
        pr.role_title.lower(): pr.user_id for pr in db_seria.project.roles
    }

    existing_roles: dict[str, Role] = {r.role_name.lower(): r for r in db_seria.roles}

    project_title = db_seria.project.title
    series_title = db_seria.title
    now = datetime.now()

    for role_name in parser.roles:
        srt_filename = generate_srt_filename(project_title, series_title, role_name)
        srt_url = None

        new_srt_content = parser.get_role_content(
            role_name,
            project_description=project_title,
            series_description=series_title,
            output_format="srt",
        )

        role_lower = role_name.lower()

        if role_lower in existing_roles:
            existing_role = existing_roles[role_lower]

            old_full_path = BASE_DIR / existing_role.srt_url.lstrip("/")
            old_content = (
                old_full_path.read_text("utf-8") if old_full_path.exists() else ""
            )

            if old_content != new_srt_content:
                srt_url = save_srt_content(
                    new_srt_content.encode("utf-8"), srt_filename
                )
                existing_role.srt_url = srt_url
                existing_role.checked = False

                db.add(
                    Fix(
                        role_id=existing_role.role_id,
                        phrase=0,
                        note=f"был обновлён srt файл {now.strftime('%d.%m.%Y %H:%M')}",
                        ready=False,
                    )
                )
                db.add(
                    AssFile(series_id=seria_id, fix_note=f"Обновлена роль: {role_name}")
                )
        else:
            srt_url = save_srt_content(new_srt_content.encode("utf-8"), srt_filename)
            actor_user_id = project_roles_lookup.get(role_lower)

            db.add(
                Role(
                    role_name=role_name,
                    series_id=seria_id,
                    user_id=actor_user_id if actor_user_id is not None else null(),
                    srt_url=srt_url,
                    checked=False,
                    timed=False,
                    state=RoleState.NOT_LOADED,
                )
            )
            if had_subs:
                db.add(AssFile(series_id=seria_id, fix_note=f"Добавлена роль: {role_name}"))

    await db.commit()

    # Reading roles and fixes again to get non-touched ones and updated fixes
    all_roles = (
        await db.scalars(
            select(Role)
            .where(Role.series_id == seria_id)
            .options(
                selectinload(Role.user),
                selectinload(Role.fixes),
                selectinload(Role.records),
            )
        )
    ).all()

    all_ass_fixes = (
        await db.scalars(select(AssFile).where(AssFile.series_id == seria_id))
    ).all()

    roles_response = [
        RoleSubsResponse(
            id=role.role_id,
            role_name=role.role_name,
            actor=(
                ActorSubsResponse(
                    user_id=role.user.user_id,
                    nickname=role.user.nickname,
                    avatar_url=role.user.avatar_url,
                    is_active=role.user.is_active,
                )
                if role.user is not None and role.user.user_id != -1
                else None
            ),
            fixes=[
                FixSubsResponse(id=f.id, phrase=f.phrase, note=f.note, ready=f.ready)
                for f in role.fixes
            ],
            note=role.note,
            checked=role.checked,
            timed=role.timed,
            state=compute_role_state(role).value,
            subtitle=role.srt_url,
            records=[
                RecordSubsResponse(
                    id=rec.id,
                    record_title=rec.record_prev_title,
                    record_note=None,
                    record_url=rec.record_url,
                )
                for rec in role.records
            ],
        )
        for role in all_roles
    ]

    return SubsUpdateResponse(
        ass_file=AssFileSubsResponse(
            ass_file_url=ass_url,
            ass_fixes=[
                AssFixItemResponse(fix_id=af.fix_id, fix_note=af.fix_note)
                for af in all_ass_fixes
            ],
        ),
        roles=roles_response,
    )


@router.post(
    "/{seria_id}/subs/fix",
    response_model=AssFixCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subs_fix(
    data: AssFixCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SubsAccessChecker())],
) -> AssFile:
    db_fix = AssFile(series_id=db_seria.id, fix_note=data.fix_note)
    db.add(db_fix)
    await db.commit()
    await db.refresh(db_fix)
    return db_fix


@router.patch("/subs/fix/{fix_id}", response_model=AssFixCreateResponse)
async def update_subs_fix(
    data: AssFixCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_fix: Annotated[AssFile, Depends(AssFixAccessChecker())],
) -> AssFile:
    db_fix.fix_note = data.fix_note
    await db.commit()
    await db.refresh(db_fix)
    return db_fix


@router.delete("/subs/fix/{fix_id}", response_model=str)
async def delete_subs_fix(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_fix: Annotated[AssFile, Depends(AssFixAccessChecker())],
) -> str:
    await db.delete(db_fix)
    await db.commit()
    return "Фикс субтитров успешно удалён"


@router.post(
    "/{seria_id}/role",
    response_model=RoleCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_series_role(
    data: RoleCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesRoleCreateAccessChecker())],
) -> RoleCreateResponse:
    existing = await db.scalar(
        select(Role).where(
            Role.series_id == db_seria.id,
            Role.role_name.ilike(data.role_name),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Роль с таким названием уже создана",
        )

    db_seria_full = await db.scalar(
        select(Series)
        .where(Series.id == db_seria.id)
        .options(selectinload(Series.project).selectinload(ProjectModel.roles))
    )

    if db_seria_full is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
        )

    project_roles_lookup: dict[str, int] = {
        pr.role_title.lower(): pr.user_id for pr in db_seria_full.project.roles
    }

    role_lower = data.role_name.lower()
    actor_user_id: int | None = None
    actor: ActorCreateResponse | None = None

    if role_lower in project_roles_lookup:
        actor_user_id = project_roles_lookup[role_lower]
        db_actor = await db.get(UserModel, actor_user_id)
        if db_actor is not None and db_actor.user_id != -1:
            actor = ActorCreateResponse(
                id=db_actor.user_id,
                nickname=db_actor.nickname,
                avatar_url=db_actor.avatar_url,
            )
        else:
            actor_user_id = None

    new_role = Role(
        role_name=data.role_name,
        series_id=db_seria.id,
        user_id=actor_user_id if actor_user_id is not None else null(),
        srt_url="",
        checked=False,
        timed=False,
        state=RoleState.NOT_LOADED,
    )
    db.add(new_role)
    await db.commit()
    await db.refresh(new_role)

    return RoleCreateResponse(
        id=new_role.role_id,
        role_name=new_role.role_name,
        actor=actor,
        fixes=None,
        note=new_role.note or "",
        checked=new_role.checked,
        timed=new_role.timed,
        state=new_role.state.value,
        subtitle=None,
        records=None,
    )


@router.delete("/role/{role_id}", response_model=str)
async def delete_series_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_role: Annotated[Role, Depends(SeriesRoleDeleteAccessChecker())],
) -> str:
    delete_role_srt(db_role)

    await db.delete(db_role)
    await db.commit()
    return "Роль успешно удалена из серии"


@router.put("/role/{role_id}/actor", response_model=RoleActorResponse)
async def set_role_actor(
    data: RoleActorUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_role: Annotated[Role, Depends(SeriesRoleActorSetAccessChecker())],
) -> RoleActorResponse:
    if data.actor_id is None:
        db_role.user_id = null()
        await db.commit()
        return RoleActorResponse(user_id=None, nickname=None, avatar_url=None)

    actor = await db.get(UserModel, data.actor_id)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден."
        )

    db_role.user_id = data.actor_id

    db_seria = await db.get(Series, db_role.series_id)
    if db_seria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Серия не найдена."
        )

    project_role_history_entry = await db.scalar(
        select(ProjectRoleHistory).where(
            ProjectRoleHistory.project_id == db_seria.project_id,
            ProjectRoleHistory.role_title.ilike(db_role.role_name),
        )
    )
    if project_role_history_entry is None:
        project_role_history_entry = ProjectRoleHistory(
            project_id=db_seria.project_id,
            role_title=db_role.role_name,
            user_id=data.actor_id,
            image_url="",
        )
        db.add(project_role_history_entry)
    else:
        project_role_history_entry.user_id = data.actor_id

    await db.commit()

    return RoleActorResponse(
        user_id=actor.user_id,
        nickname=actor.nickname,
        avatar_url=actor.avatar_url,
    )


@router.patch("/role/{role_id}/state", response_model=RoleStateResponse)
async def update_role_state(
    data: RoleStateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_role: Annotated[Role, Depends(SeriesRoleStateAccessChecker())],
) -> RoleStateResponse:
    if data.checked is not None:
        db_role.checked = data.checked
    if data.timed is not None:
        db_role.timed = data.timed
    await db.flush()

    role_full = await db.scalar(
        select(Role)
        .where(Role.role_id == db_role.role_id)
        .options(selectinload(Role.records), selectinload(Role.fixes))
    )
    if role_full is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    new_state = compute_role_state(role_full)
    db_role.state = new_state
    await db.commit()

    return RoleStateResponse(
        checked=db_role.checked,
        timed=db_role.timed,
        state=new_state.value,
    )


@router.put("/role/{role_id}/subtitle", response_model=RoleSubtitleResponse)
async def update_role_subtitle(
    srt_file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_role: Annotated[Role, Depends(SeriesRoleSubtitleAccessChecker())],
) -> RoleSubtitleResponse:
    role_with_series_and_project = await db.scalar(
        select(Role)
        .where(Role.role_id == db_role.role_id)
        .options(selectinload(Role.series).selectinload(Series.project))
    )
    if role_with_series_and_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    if srt_file.filename is None or not srt_file.filename.lower().endswith(".srt"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл должен быть .srt")

    srt_file.filename = generate_srt_filename(
        project_title=role_with_series_and_project.series.project.title,
        seria_title=role_with_series_and_project.series.title,
        role_name=role_with_series_and_project.role_name,
    )
    srt_url = await save_srt(srt_file)
    db_role.srt_url = srt_url
    db_role.checked = False

    now = datetime.now()
    db.add(
        Fix(
            role_id=db_role.role_id,
            phrase=0,
            note=f"был обновлён srt файл {now.strftime('%d.%m.%Y %H:%M')}",
            ready=False,
        )
    )
    await db.flush()

    role_full = await db.scalar(
        select(Role)
        .where(Role.role_id == db_role.role_id)
        .options(selectinload(Role.records), selectinload(Role.fixes))
    )
    if role_full is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    new_state = compute_role_state(role_full)
    db_role.state = new_state
    await db.commit()

    return RoleSubtitleResponse(
        subtitle=db_role.srt_url,
        state=new_state.value,
        checked=db_role.checked,
        fixes=[
            RoleSubtitleFixResponse(id=f.id, phrase=f.phrase, note=f.note, ready=f.ready)
            for f in role_full.fixes
        ],
    )


@router.post(
    "/role/{role_id}/records",
    response_model=RecordAddResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_role_record(
    record_file: UploadFile,
    record_title: Annotated[str, Form()],
    db: Annotated[AsyncSession, Depends(get_db)],
    db_role: Annotated[Role, Depends(SeriesRoleRecordAccessChecker())],
    note: Annotated[Optional[str], Form()] = None,
) -> RecordAddResponse:
    record_url = await save_record(record_file, record_title)

    db_record = Record(
        role_id=db_role.role_id,
        record_url=record_url,
        record_prev_title=record_title,
        record_note=note if note is not None else null(),
    )
    db.add(db_record)
    await db.flush()

    role_full = await db.scalar(
        select(Role)
        .where(Role.role_id == db_role.role_id)
        .options(selectinload(Role.records), selectinload(Role.fixes))
    )
    if role_full is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    role_full.timed = False
    role_full.checked = False
    new_state = compute_role_state(role_full)
    db_role.state = new_state
    await db.commit()
    await db.refresh(db_record)

    return RecordAddResponse(
        record=RecordItemResponse(
            id=db_record.id,
            record_title=db_record.record_prev_title,
            record_note=db_record.record_note,
            record_url=db_record.record_url,
        ),
        state=new_state.value,
    )


@router.delete("/role/records/{record_id}", response_model=RecordDeleteResponse)
async def delete_role_record(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_record: Annotated[Record, Depends(SeriesRoleRecordDeleteAccessChecker())],
) -> RecordDeleteResponse:
    role_id = db_record.role_id

    record_path = BASE_DIR / db_record.record_url.lstrip("/")
    record_path.unlink(missing_ok=True)

    await db.delete(db_record)
    await db.flush()

    role_full = await db.scalar(
        select(Role)
        .where(Role.role_id == role_id)
        .options(selectinload(Role.records), selectinload(Role.fixes))
    )
    if role_full is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    role_full.timed = False
    role_full.checked = False
    new_state = compute_role_state(role_full)
    role_full.state = new_state
    await db.commit()

    return RecordDeleteResponse(state=new_state.value)


@router.patch("/role/{role_id}/note", response_model=RoleNoteResponse)
async def update_role_note(
    body: RoleNoteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    db_role: Annotated[Role, Depends(SeriesRoleRecordAccessChecker())],
) -> RoleNoteResponse:
    db_role.note = body.note
    await db.commit()
    return RoleNoteResponse(note=db_role.note)


@router.delete("/{seria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series(
    db: Annotated[AsyncSession, Depends(get_db)],
    db_seria: Annotated[Series, Depends(SeriesAccessChecker())],
):
    await delete_series_subs(db, db_seria)

    await db.delete(db_seria)
    await db.commit()

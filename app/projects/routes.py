from fastapi import (
    APIRouter,
    status,
    Request,
    UploadFile,
    Depends,
    HTTPException,
    Query,
    Body,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_
from sqlalchemy.orm import selectinload
from app.projects.utils import (
    upd_project_cover,
    get_db_project,
    update_role_image,
    delete_role_image,
    delete_project_cover,
    ProjectChecker,
    AccessChecker,
)
from app.database import get_db
from .models import (
    Project as ProjectModel,
    ProjectLink,
    ProjectUser,
    Project,
    ProjectRoleHistory,
)
from app.users.models import User as UserModel
from .schemas import (
    ProjectResponse,
    ProjectCreate,
    ProjectsResponse,
    status_list,
    ProjectLinkCreate,
    RoleCreate,
    ProjectTitleUpdate,
    ProjectStatusUpdate,
    ProjectCuratorUpdate,
    ProjectParticipantCreate,
    ProjectDescriptionUpdate,
    ProjectParticipantsResponse,
    voice_types,
    ProjectTypeUpdate,
)
from app.users.utils import (
    get_max_lvl,
    get_current_user,
    check_curator,
)
from app.users.schemas import UsersResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectsResponse])
async def get_projects(
    user_id: int = Query(default=None),
    is_participating: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Возвращает список всех проектов.\n
    Если указан user_id, то вернутся проекты в которых участвует пользователь.\n
    Если null, соответственно, все проекты.

    """
    stmt = select(ProjectModel).options(selectinload(ProjectModel.participants))
    if is_participating:
        stmt = stmt.join(Project.participants).where(UserModel.user_id == user.user_id)
    if user_id:
        stmt = stmt.outerjoin(ProjectUser)
        if not await db.scalar(select(UserModel).where(UserModel.user_id == user_id)):
            raise HTTPException(status_code=404, detail="User not found")
        stmt = stmt.where(
            or_(ProjectModel.curator_id == user_id, ProjectUser.user_id == user_id)
        )
    db_projects = await db.scalars(stmt)
    projects = db_projects.all()

    return [
        {
            "project_id": project.project_id,
            "title": project.title,
            "status": project.status,
            "image_url": project.image_url,
            "participants": [
                participant.user_id for participant in project.participants
            ]
            + [project.curator_id],
        }
        for project in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_db_project(project_id, db)

    return project


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_project(
    image: UploadFile | None = None,
    project: ProjectCreate = Depends(ProjectCreate.as_form),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
    check_access=Depends(AccessChecker()),
):
    """
    Создаёт новый проект.\n
    Эндопинт 2лвл+.\n
    Список участников ожидается в виде списка никнеймов.\n
    type принимает только "закадр", "рекаст", "дубляж"\n
    status принимает только "подготовка", "в работе", "завершён", "приостановлен", "закрыт"\n
    """
    new_project = ProjectModel(**project.model_dump())

    if image:
        image_url = await upd_project_cover(image, None)
        new_project.image_url = image_url

    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)

    return new_project


@router.patch("/{project_id}/title")
async def update_project_title(
    project_id: int,
    title: ProjectTitleUpdate,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    db_project.title = title.title
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.put("/{project_id}/status")
async def update_project_status(
    project_id: int,
    status: ProjectStatusUpdate,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    db_project.status = status.status
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)

    return upd_project


@router.put("/{project_id}/curator")
async def update_project_curator(
    project_id: int,
    curator: ProjectCuratorUpdate,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    new_curator = await db.get(UserModel, curator.curator_id)
    if not new_curator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден."
        )

    db_project.curator_id = curator.curator_id
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)

    return upd_project


@router.put("/{project_id}/cover")
async def update_project_cover(
    project_id: int,
    cover_image: UploadFile,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    db_project.image_url = await upd_project_cover(cover_image, db_project.image_url)
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.post("/{project_id}/participants")
async def add_project_participant(
    project_id: int,
    participant: ProjectParticipantCreate,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    new_participant = await db.get(UserModel, participant.participant_id)
    if not new_participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Такого пользователя не существует.",
        )

    new_participation = ProjectUser(
        user_id=participant.participant_id, project_id=project_id
    )
    db.add(new_participation)
    await db.commit()
    await db.refresh(new_participation)

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.delete("/{project_id}/participants/{participant_id}")
async def delete_project_participant(
    project_id: int,
    participant_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    participation = await db.scalar(
        select(ProjectUser).where(
            ProjectUser.user_id == participant_id, ProjectUser.project_id == project_id
        )
    )
    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Участник не найден."
        )
    await db.delete(participation)
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.post("/{project_id}/links")
async def add_project_link(
    project_id: int,
    link: ProjectLinkCreate,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    db_link = ProjectLink(**link.model_dump(), project_id=project_id)

    db.add(db_link)
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.patch("/{project_id}/description")
async def update_project_description(
    project_id: int,
    description: ProjectDescriptionUpdate,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
):
    db_project.description = description.description
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.delete("/{project_id}/links/{link_id}")
async def delete_project_link(
    project_id: int,
    link_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    db_link = await db.get(ProjectLink, link_id)
    if not db_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ссылка не найдена."
        )

    await db.delete(db_link)
    await db.commit()
    await db.refresh(db_link)

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    if db_project.image_url:
        await delete_project_cover(db_project.image_url)

    await db.delete(db_project)
    await db.commit()

    return "Проект успешно удалён."


@router.post("/{project_id}/roles")
async def add_role(
    project_id: int,
    image: UploadFile,
    role: RoleCreate = Depends(RoleCreate.as_form),
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    if image:
        image_url = await update_role_image(image)

    new_db_role = ProjectRoleHistory(
        **role.model_dump(), image_url=image_url, project_id=project_id
    )
    db.add(new_db_role)
    await db.commit()

    upd_project = await get_db_project(project_id, db)
    return upd_project


@router.delete("/{project_id}/roles/{role_id}")
async def remove_role(
    project_id: int,
    role_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    db_role = await db.get(ProjectRoleHistory, role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена."
        )

    if db_role.image_url:
        delete_role_image(db_role.image_url)

    await db.delete(db_role)
    await db.commit()

    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)

    return upd_project


@router.get("/{project_id}/participants", response_model=list[UsersResponse])
async def get_project_participants(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    db_project = await db.scalar(
        select(ProjectModel)
        .where(ProjectModel.project_id == project_id)
        .options(
            selectinload(ProjectModel.participants).options(
                selectinload(UserModel.team_roles),
                selectinload(UserModel.contacts),
            )
        )
    )
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден."
        )

    project_participants = list(db_project.participants)
    project_curator = await db.scalar(
        select(UserModel)
        .where(UserModel.user_id == db_project.curator_id)
        .options(
            selectinload(UserModel.team_roles),
            selectinload(UserModel.contacts),
        )
    )
    project_participants.append(project_curator)

    return project_participants


@router.patch("/{project_id}/type")
async def update_type(
    type: ProjectTypeUpdate,
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
    db_project: ProjectModel = Depends(ProjectChecker()),
    check_access=Depends(AccessChecker()),
):
    db_project.type = type.type
    await db.commit()
    await db.refresh(db_project)

    upd_project = await get_db_project(project_id, db)

    return upd_project

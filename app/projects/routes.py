from fastapi import APIRouter, status, Request, Depends, HTTPException, Query
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from .models import Project as ProjectModel, ProjectLink, ProjectUser, Project
from app.users.models import User as UserModel
from .schemas import ProjectResponse, ProjectCreate
from app.users.utils import (
    get_max_lvl,
    get_current_user,
    check_curator,
    check_admin,
    check_senior_admin,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectResponse])
async def get_projects(
    participation: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Возвращает список всех проектов.\n
    Если participation = True, пользователь получит только те проекты, в которых он участвует.\n
    Если False, соответственно, все проекты.

    """
    if not participation:
        projects = await db.scalars(
            select(ProjectModel).where(ProjectModel.is_active == True)
        )

    else:
        projects = await db.scalars(
            select(ProjectModel)
            .join(ProjectUser, ProjectModel.project_id == ProjectUser.project_id)
            .where(ProjectUser.user_id == user.user_id, ProjectModel.is_active == True)
        )

    res = projects.all()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Проектов ещё не существует"
        )

    result = []
    for project in res:
        curator = await db.scalar(
            select(UserModel).where(
                UserModel.is_active == True,
                UserModel.user_id == project.curator,
            )
        )
        response = ProjectResponse(
            project_id=project.project_id,
            title=project.title,
            type=project.type,
            curator=curator.nickname,
            image_url=project.image_url,
            created_at=project.created_at,
            is_active=project.is_active,
            status=project.status,
        )
        result.append(response)
    return result


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Создаёт новый проект.\n
    Эндопинт 2лвл+.\n
    Список участников ожидается в виде списка никнеймов.\n
    type принимает только "закадр", "рекаст", "дубляж"\n
    status принимает только "подготовка", "в работе", "завершён", "приостановлен", "закрыт"\n
    """
    participants = []
    if not await get_max_lvl(db, user) >= 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только кураторы и администраторы могут создавать проекты.",
        )

    for participant in project.participants:
        db_participant = await db.scalar(
            select(UserModel).where(
                UserModel.nickname == participant, UserModel.is_active == True
            )
        )
        if not db_participant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с ником {participant} не найден.",
            )
        participants.append(db_participant)

    curator = await db.scalar(
        select(UserModel).where(
            UserModel.is_active == True, UserModel.nickname == project.curator
        )
    )
    if not curator or not check_curator(db, curator):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Куратор не существует"
        )
    new_project = ProjectModel(
        title=project.title,
        type=project.type,
        curator=curator.user_id,
        image_url=project.image_url,
        created_at=project.created_at,
        status=project.status,
    )

    db.add(new_project)
    await db.flush()
    await db.refresh(new_project)

    for participant in participants:
        new_db_participant = ProjectUser(
            user_id=participant.user_id, project_id=new_project.project_id
        )

        db.add(new_db_participant)

    for link in project.links:
        new_db_link = ProjectLink(
            project_id=new_project.project_id, title=link.title, url=link.url
        )

        db.add(new_db_link)

    await db.commit()
    response = ProjectResponse(
        project_id=new_project.project_id,
        title=new_project.title,
        type=new_project.type,
        curator=curator.nickname,
        image_url=new_project.image_url,
        created_at=new_project.created_at,
        is_active=new_project.is_active,
        status=new_project.status,
    )
    return response


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    updated_project: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Эндпоинт для редактирования проекта. \n
    Только 2+ лвл доступа. \n
    """
    if not await get_max_lvl(db, user) >= 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только куратор и выше может редактировать проект",
        )

    upd_project = await db.scalar(
        select(ProjectModel).where(
            ProjectModel.project_id == project_id, ProjectModel.is_active == True
        )
    )
    if not upd_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден."
        )

    participants = []
    for participant in updated_project.participants:
        db_participant = await db.scalar(
            select(UserModel).where(
                UserModel.nickname == participant, UserModel.is_active == True
            )
        )
        if not db_participant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с ником {participant} не найден.",
            )
        participants.append(db_participant)
        print("im here", participants)

    stmt = await db.scalars(
        select(UserModel)
        .join(ProjectUser, UserModel.user_id == ProjectUser.user_id)
        .where(ProjectUser.project_id == project_id)
    )

    curr_participants = stmt.all()
    # удаление участников из проекта
    for participant in curr_participants:
        if participant.nickname not in updated_project.participants:
            db_participant = await db.scalar(
                select(ProjectUser).where(
                    ProjectUser.user_id == participant.user_id,
                    ProjectModel.project_id == project_id,
                )
            )
            await db.delete(db_participant)

    # добавление новых участников в проект
    for participant in participants:
        if participant.user_id in [p.user_id for p in curr_participants]:
            continue
        else:
            new_db_participant = ProjectUser(
                user_id=participant.user_id, project_id=project_id
            )
            db.add(new_db_participant)

    stmt = await db.scalars(
        select(ProjectLink).where(
            ProjectLink.project_id == project_id, ProjectLink.is_active == True
        )
    )

    links = stmt.all()

    # мягкое удаление ссылок:
    for link in links:
        if link.url not in [p.url for p in updated_project.links]:
            db_link_for_delete = await db.scalar(
                select(ProjectLink).where(
                    ProjectLink.url == link.url,
                    ProjectLink.project_id == project_id,
                    ProjectLink.is_active == True,
                )
            )
            if db_link_for_delete:
                db_link_for_delete.is_active = False

    # добавление новых ссылок
    for link in updated_project.links:
        if link.url in [x.url for x in links]:
            continue
        else:
            new_db_link = ProjectLink(**link.model_dump(), project_id=project_id)
            db.add(new_db_link)

    curator = await db.scalar(
        select(UserModel).where(
            UserModel.is_active == True, UserModel.nickname == updated_project.curator
        )
    )
    if not curator or not await check_curator(db, curator):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Куратор не существует"
        )
    await db.execute(
        update(ProjectModel)
        .where(ProjectModel.project_id == project_id)
        .values(
            title=updated_project.title,
            type=updated_project.type,
            curator=curator.user_id,
            image_url=updated_project.image_url,
            created_at=updated_project.created_at,
            status=updated_project.status,
        )
    )

    await db.commit()

    await db.refresh(upd_project)

    response = ProjectResponse(
        project_id=upd_project.project_id,
        title=updated_project.title,
        type=updated_project.type,
        curator=curator.nickname,
        image_url=updated_project.image_url,
        created_at=updated_project.created_at,
        is_active=upd_project.is_active,
        status=upd_project.status,
    )
    return response


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Эндпоинт для мягкого удаления проекта.
    Доступен только 2+ лвл.
    """
    if not await get_max_lvl(db, user) >= 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только куратор и выше может удалить проект",
        )

    project = await db.scalar(
        select(ProjectModel).where(
            ProjectModel.project_id == project_id, ProjectModel.is_active == True
        )
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден."
        )

    db_links = await db.scalars(
        select(ProjectLink).where(
            ProjectLink.project_id == project_id, ProjectLink.is_active == True
        )
    )
    # Мягкое удаление ссылок
    links = db_links.all()
    for link in links:
        link.is_active = False
    # удаление связей с пользователями
    db_participants = await db.scalars(
        select(ProjectUser).where(ProjectUser.project_id == project_id)
    )
    participants = db_participants.all()
    if participants:
        for participant in participants:
            await db.delete(participant)

    project.is_active = False
    await db.commit()

    return "Проект был успешно удалён."

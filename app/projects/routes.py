from fastapi import APIRouter, status, Request, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from .models import Project as ProjectModel, ProjectLink
from app.users.models import User as UserModel
from ..users import get_current_user
from .schemas import ProjectResponse, ProjectCreate

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
        projects = await db.scalars()

    res = projects.all()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Проектов ещё не существует"
        )

    return res


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    pass

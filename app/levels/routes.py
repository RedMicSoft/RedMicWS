from fastapi import APIRouter, FastAPI, status, HTTPException, Depends
from .schemas import LevelCreate, LevelResponse
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Level as LevelModel
from sqlalchemy import select, update

from ..users import User as UserModel, get_current_user, get_max_lvl

router = APIRouter(
    tags=["levels"],
    prefix="/levels",
)


@router.get("/", response_model=list[LevelResponse])
async def get_levels(db: AsyncSession = Depends(get_db)):
    """
    Возвращает все роли.
    """
    levels = await db.scalars(select(LevelModel).where(LevelModel.is_active == True))

    return levels.all()


@router.get("/{id}", response_model=LevelResponse)
async def get_level(id: int, db: AsyncSession = Depends(get_db)):
    """Возвращает инфу об одной роли"""
    level = await db.scalar(
        select(LevelModel).where(
            LevelModel.level_id == id, LevelModel.is_active == True
        )
    )
    if not level:
        raise HTTPException(status_code=404, detail="Level not found")

    return level


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=LevelResponse)
async def create_level(
    level: LevelCreate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Только для главного админа.\n
    Создаёт новую роль в БД.
    """
    if await get_max_lvl(db, user) < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only main admins can perform this action",
        )
    new_lvl = LevelModel(**level.model_dump())
    db.add(new_lvl)
    await db.commit()
    await db.refresh(new_lvl)

    return new_lvl


@router.put("/{id}", response_model=LevelResponse, status_code=status.HTTP_200_OK)
async def update_level(
    level: LevelCreate,
    id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Только для гл. админа.\n
    Обновляет категорию по её id.
    """
    if await get_max_lvl(db, user) < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only main admins can perform this action",
        )

    current_level = await db.scalar(
        select(LevelModel).where(
            LevelModel.level_id == id,
            LevelModel.is_active == True,
        )
    )
    if not current_level:
        raise HTTPException(status_code=404, detail="Level not found")

    await db.execute(
        update(LevelModel).where(LevelModel.level_id == id).values(**level.model_dump())
    )
    await db.commit()
    return current_level


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_level(
    id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Только для гл. админа\n
    Удаляет категорию по её id.
    """
    user_access = max([lvl for lvl in user.levels])
    if user_access < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only main admins can perform this action",
        )

    current_level = await db.scalar(
        select(LevelModel).where(
            LevelModel.level_id == id,
            LevelModel.is_active == True,
        )
    )
    if not current_level:
        raise HTTPException(status_code=404, detail="Level not found")

    current_level.is_active = False

    return "Level deleted"

from fastapi import APIRouter, FastAPI, status, HTTPException, Depends
from .schemas import LevelCreate, LevelResponse
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Level as LevelModel, UserLevel
from sqlalchemy import select, update, delete

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
        raise HTTPException(status_code=404, detail="Роль не найдена.")

    return level


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=LevelResponse)
async def create_level(
    level: LevelCreate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Только для 3,4 лвлов.\n
    Создаёт новую роль в БД.
    """
    if await get_max_lvl(db, user) < 4 and level.access_level >= 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только гл. админы могут создавать новые админские роли.",
        )

    if await get_max_lvl(db, user) < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут создавать роли.",
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
    Обновляет роль по её id.
    """
    if await get_max_lvl(db, user) < 4 and level.access_level >= 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только гл. админы могут обновлять админские роли.",
        )
    if await get_max_lvl(db, user) < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут обновлять роли.",
        )

    current_level = await db.scalar(
        select(LevelModel).where(
            LevelModel.level_id == id,
            LevelModel.is_active == True,
        )
    )
    if not current_level:
        raise HTTPException(status_code=404, detail="Роль не найдена.")

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
    Удаляет роль по её id.
    """

    current_level = await db.scalar(
        select(LevelModel).where(
            LevelModel.level_id == id,
            LevelModel.is_active == True,
        )
    )
    if not current_level:
        raise HTTPException(status_code=404, detail="Роль не найдена")

    if await get_max_lvl(db, user) < 4 and current_level.access_level >= 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только гл. админы могут удалять админские роли.",
        )
    if await get_max_lvl(db, user) < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут удалять роли.",
        )

    current_level.is_active = False

    users_levels_for_delete = delete(UserLevel).where(UserLevel.level_id == id)
    result = await db.execute(users_levels_for_delete)

    await db.commit()

    return "Роль успешно удалена."

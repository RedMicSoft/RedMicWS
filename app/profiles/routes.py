from fastapi import APIRouter, status, Depends, HTTPException
from .models import Profile as ProfileModel
from .schemas import ProfileResponse, ProfileCreate
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from ..users import User as UserModel, get_current_user

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
)


@router.get("/", response_model=list[ProfileResponse])
async def get_profiles(db: AsyncSession = Depends(get_db)):
    """
    Получить список всех профилей
    """


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProfileResponse,
    summary="Create a new profile",
)
async def create_profile(
    profile: ProfileCreate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """
    Создаёт новый профиль, связанный с таблицей users.\n
    По сути в данном эндпоинте обязательно требуется от пользователя указать только свою роль.\n
    Под ролью подразумевается актер, куратор и тп, просто для обозначения этого человека(не опред уровень доступа)\n
    Всё остальное опционально.(Предполагается что user_id для связи берётся из jwt, т.к. он соотв user_id в БД)\n
    *user_id\n
    avatar_url\n
    age\n
    birth_date\n
    *role\n
    """
    new_profile = ProfileModel(**profile.model_dump(), user_id=user.user_id)

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return new_profile

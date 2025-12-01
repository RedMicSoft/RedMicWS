from fastapi import APIRouter, status, Depends, HTTPException
from .models import Profile as ProfileModel
from .schemas import ProfileResponse, ProfileCreate
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from ..users import User as UserModel, get_current_user
from sqlalchemy import select

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
)


@router.get("/", response_model=list[ProfileResponse])
async def get_profiles(db: AsyncSession = Depends(get_db)):
    """
    Получить список всех профилей
    """
    profiles = await db.scalars(
        select(ProfileModel).where(ProfileModel.is_active == True)
    )

    return profiles.all()


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
    Создаёт новый профиль, связанный с таблицей users \n
    *user_id\n
    avatar_url\n
    age\n
    birth_date\n
    *role\n
    """
    stmt = await db.scalar(
        select(ProfileModel).where(ProfileModel.user_id == user.user_id)
    )
    if stmt:
        raise HTTPException(status_code=400, detail="Профиль уже существует")
    new_profile = ProfileModel(**profile.model_dump(), user_id=user.user_id)

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return new_profile

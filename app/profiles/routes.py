from fastapi import APIRouter, status, Depends, HTTPException, UploadFile
from .models import Profile as ProfileModel
from .schemas import ProfileResponse, ProfileCreate
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from ..users import User as UserModel, get_current_user
from sqlalchemy import select
from dateutil.relativedelta import relativedelta
from datetime import date, datetime, timedelta
from .utils import save_demo

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


@router.get("/{profile_id}")
async def get_profile_by_id(profile_id: int, db: AsyncSession = Depends(get_db)):
    db_profile = await db.scalar(
        select(ProfileModel).where(
            ProfileModel.profile_id == profile_id, ProfileModel.is_active == True
        )
    )

    return {"profile": db_profile, "is_rest": db_profile.rest}


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
    avatar\n
    birth_date\n
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


@router.post("/{profile_id}", response_model=ProfileResponse, summary="create rest")
async def update_rest(
    rest_start: datetime,
    rest_end: datetime,
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    db_user = await db.scalar(
        select(ProfileModel).where(
            ProfileModel.profile_id == profile_id, ProfileModel.is_active == True
        )
    )

    db_user.rest_start = rest_start
    db_user.rest_end = rest_end

    await db.commit()
    await db.refresh(db_user)

    return db_user


@router.put("/{profile_id}", summary="upload demo")
async def upload_demo(
    demo: UploadFile,
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    demo = await save_demo(demo)

    db_profile = await db.scalar(
        select(ProfileModel).where(
            ProfileModel.is_active == True, ProfileModel.profile_id == profile_id
        )
    )

    if not db_profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Профиль не найден")

    db_profile.demo_url = demo

    await db.commit()
    await db.refresh(db_profile)

    return db_profile

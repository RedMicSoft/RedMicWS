from fastapi import APIRouter, status, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from .schemas import UserResponse, UserCreate
from .models import User as UserModel
from .utils import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_max_lvl,
)
from sqlalchemy import select

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
async def get_users(
    db: AsyncSession = Depends(get_db), user: UserModel = Depends(get_current_user)
):
    users = await db.scalars(select(UserModel).where(UserModel.is_active == True))

    user_level = await get_max_lvl(db, user)
    if user_level < 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return users.all()


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Выводит подробную информацию о пользователе, включая список его ролей и макс левел.
    """
    current_user_level = await get_max_lvl(db, user)
    if current_user_level < 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    request_user = await db.get(UserModel, user_id)
    if not request_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return {
        "User": request_user,
        "Levels": request_user.levels,
        "Max": await get_max_lvl(db, request_user),
    }


# dev endpoint
@router.post(
    "/create", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def crt_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    dev эндопинт для взаимодействия с БД без авторизации.
    """
    db_user = await db.scalar(
        select(UserModel).where(
            UserModel.nickname == user.nickname, UserModel.is_active == True
        )
    )
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="nickname already registered",
        )

    db_user = UserModel(
        nickname=user.nickname,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: UserModel = Depends(get_current_user),
):
    """
    Эндпоинт для прода. Предполагает уже созданного админа в БД. В разработке использовать POST users/create. \n
    В users/create не нужно использовать авторизацию для создания пользователей. В проде уберем. \n
    Регистрация нового пользователя с уровнем доступа от 1 до 3 и хэш. пароля. \n
    Ошибка 400 если email уже есть в БД. \n
    Ошибка 400 если юзер не админ. \n
    Только пользователь с access_level 3 может получить доступ.
    """
    if admin.access_level < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only admins can create new users",
        )

    db_user = await db.scalar(
        select(UserModel).where(
            UserModel.nickname == user.nickname, UserModel.is_active == True
        )
    )
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    db_user = UserModel(
        nickname=user.nickname,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """
    Аутентифицирует пользователя и возвращает access_token.
    Токен длится 30 дней.
    """
    db_user = await db.scalars(
        select(UserModel).where(
            UserModel.nickname == form_data.username, UserModel.is_active == True
        )
    )
    user = db_user.first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"id": user.user_id})

    return {"access_token": access_token, "token_type": "bearer"}

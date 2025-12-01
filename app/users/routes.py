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
    check_admin,
    check_senior_admin,
)
from sqlalchemy import select
from app.levels.models import Level, UserLevel
from app.levels.schemas import LevelResponse

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

    roles = await db.scalars(
        select(Level).join(UserLevel).where(UserLevel.user_id == request_user.user_id)
    )

    return {
        "User": request_user,
        "roles": roles.all(),
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
            detail="Никнейм уже зарегистрирован",
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
    role_name: str = Query(...),
):
    """
    Эндпоинт для прода. Предполагает уже созданного админа в БД. В разработке использовать POST users/create. \n
    В users/create не нужно использовать авторизацию для создания пользователей. В проде уберем. \n
    Регистрация нового пользователя с уровнем доступа от 1 до 3 и хэш. пароля. \n
    Ошибка 400 если email уже есть в БД. \n
    Ошибка 400 если юзер не админ. \n
    Только пользователь с access_level 3 может получить доступ.
    """
    if await get_max_lvl(db, admin) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Только админы могут создавать пользователей",
        )
    print(role_name)
    role = await db.scalar(
        select(Level).where(Level.role_name == role_name, Level.is_active == True)
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Роль не найдена"
        )

    if await get_max_lvl(db, admin) == 3 and role.access_level >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Только ст. админы могут создавать новых админов",
        )

    db_user = await db.scalar(
        select(UserModel).where(
            UserModel.nickname == user.nickname, UserModel.is_active == True
        )
    )

    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Никнейм уже зарегистрирован",
        )

    db_user = UserModel(
        nickname=user.nickname,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    user_role = UserLevel(level_id=role.level_id, user_id=db_user.user_id)
    db.add(user_role)
    await db.commit()
    return {"User": db_user, "role": role}


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


#
@router.post(
    "/{user_id}/level",
    status_code=status.HTTP_200_OK,
    response_model=list[LevelResponse],
)
async def add_user_level(
    user_id: int,
    role_name: str,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Добавляет роль пользователю.\n
    Возвращает список ролей.\n
    Только для 3 лвл+.\n
    """
    if not await check_admin(db, user) and not await check_senior_admin(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут добавить пользователю роль",
        )

    db_user = await db.scalar(
        select(UserModel).where(
            UserModel.user_id == user_id, UserModel.is_active == True
        )
    )
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден."
        )

    role = await db.scalar(
        select(Level).where(Level.role_name == role_name, Level.is_active == True)
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Роль не найдена"
        )

    if role.access_level == 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Добавить роль ст. админа можно только редактированием БД.",
        )

    if role.access_level >= 3 and await get_max_lvl(db, user) == 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только ст. админы могут добавлять роли админов.",
        )

    new_role = UserLevel(level_id=role.level_id, user_id=user_id)
    db.add(new_role)
    await db.commit()
    roles_list = await db.scalars(
        select(Level).join(UserLevel).where(UserLevel.user_id == user_id)
    )

    return roles_list.all()

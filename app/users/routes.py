from fastapi import APIRouter, status, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from .schemas import UserResponse, UserCreate
from .models import User as UserModel
from .utils import hash_password, verify_password, create_access_token
from sqlalchemy import select

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
async def get_users(db: AsyncSession = Depends(get_db)):
    users = await db.scalars(select(UserModel).where(UserModel.is_active == True))

    return users.all()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Регистрация нового пользователя с уровнем доступа от 1 до 3 и хэш. пароля.
    Ошибка 400 если email уже есть в БД
    """
    db_user = await db.scalar(
        select(UserModel).where(
            UserModel.email == user.email, UserModel.is_active == True
        )
    )
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    db_user = UserModel(
        email=user.email,
        hashed_password=hash_password(user.password),
        access_level=user.access_level,
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
    """
    db_user = await db.scalars(
        select(UserModel).where(
            UserModel.email == form_data.username, UserModel.is_active == True
        )
    )
    user = db_user.first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"id": user.user_id, "sub": user.email, "role": user.access_level}
    )

    return {"access_token": access_token, "token_type": "bearer"}

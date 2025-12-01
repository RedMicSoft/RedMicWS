from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


from app.database import get_db
from .models import User as UserModel

from app.levels.models import UserLevel, Level as LevelModel

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_TOKEN_EXPIRE_DAYS = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")
SECRET_KEY = "RedMicWorkSpaceRMWS"
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """
    Преобразует пароль в хеш с использованием bcrypt.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, соответствует ли введённый пароль сохранённому хешу.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """
    создаёт JWT с id, exp
    """
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    """
    Проверяет JWT и возвращает пользователя из базы.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception
    result = await db.scalars(
        select(UserModel).where(
            UserModel.user_id == user_id, UserModel.is_active == True
        )
    )
    user = result.first()
    if user is None:
        raise credentials_exception
    return user


async def get_max_lvl(db: AsyncSession, user: UserModel) -> int:
    stmt = await db.scalars(
        select(LevelModel).join(UserLevel).where(UserLevel.user_id == user.user_id)
    )
    res = stmt.all()
    if res:
        return max([level.access_level for level in res])
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="У пользователя нет ролей."
        )


async def check_admin(db: AsyncSession, user: UserModel) -> bool:
    return await get_max_lvl(db, user) == 3


async def check_senior_admin(db: AsyncSession, user: UserModel) -> bool:
    return await get_max_lvl(db, user) == 4

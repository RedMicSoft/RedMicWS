import time

from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, date
import jwt
from fastapi import Depends, HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


from app.database import get_db, async_session_maker
from .models import User as UserModel

from app.levels.models import UserLevel, Level as LevelModel

scheduler = AsyncIOScheduler()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_TOKEN_EXPIRE_DAYS = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")
SECRET_KEY = "RedMicWorkSpaceRMWS"
ALGORITHM = "HS256"

MEDIA_DIR = Path(__file__).resolve().parent.parent.parent / "media"


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


async def check_curator(db: AsyncSession, user: UserModel) -> bool:
    return await get_max_lvl(db, user) == 2


BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media"


async def save_demo(demo: UploadFile) -> str:
    if not demo.filename.endswith(".mp4"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Демо должно быть в формате .mp4"
        )

    directory = MEDIA_DIR / "demo"
    directory.mkdir(parents=True, exist_ok=True)

    content = await demo.read()
    file_path = MEDIA_ROOT / "demo" / demo.filename
    file_path.write_bytes(content)

    return f"/media/demo/{demo.filename}"


async def save_avatar(avatar: UploadFile) -> str:
    if not avatar.filename.endswith((".webp", ".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Неверный формат аватарки"
        )

    directory = MEDIA_DIR / "avatars"
    directory.mkdir(parents=True, exist_ok=True)

    content = await avatar.read()
    file_path = MEDIA_ROOT / "avatars" / avatar.filename
    file_path.write_bytes(content)

    return f"/media/avatars/{avatar.filename}"


async def check_and_update_rest():
    async with async_session_maker() as db:
        stmt = (
            update(UserModel)
            .where(UserModel.rest_end <= date.today())
            .values(
                rest_start=None,
                rest_end=None,
                rest_reason=None,
                is_active=True,
            )
        )
        await db.execute(stmt)
        await db.commit()


scheduler.add_job(
    check_and_update_rest, CronTrigger(hour=0, minute=0), id="daily_rest_check"
)


async def get_id_deleted_user():
    async with async_session_maker() as db:
        del_user = await db.scalar(
            select(UserModel).where(UserModel.nickname == "deleted")
        )

    return del_user.user_id

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.database import get_db
from app.series.schemas import SeriesResponse
from app.users.utils import get_current_user
from app.roles.schemas import RoleCreate
from ..users.models import User as UserModel
from .utils import save_srt

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media"
router = APIRouter(prefix="/series", tags=["series"])

print(BASE_DIR)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=SeriesResponse)
async def create_series(
    srts: list[UploadFile],
    roles: RoleCreate = Depends(RoleCreate.as_form),
    db: AsyncSession = Depends(get_db),
    UserModel=Depends(get_current_user),
):
    for i in srts:
        await save_srt(i)

    return "success"

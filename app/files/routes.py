from fastapi import APIRouter, UploadFile, Depends, HTTPException, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.files.schemas import FileResponse
from app.files.utils import save_file, CustomStaticFiles, FileModel, file_delete
from app.users.models import User
from app.users.utils import get_current_user, get_max_lvl
from app.database import get_db

router = APIRouter(
    tags=["files"],
    prefix="/files",
)


@router.get("/")
async def get_files(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    db_files = await db.scalars(select(FileModel))
    files = db_files.all()

    return files


@router.post("/", response_model=FileResponse)
async def upload_file(
    file: UploadFile,
    filename: str = Form(...),
    category: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут загружать файлы.",
        )

    db_file = FileModel(**(await save_file(file)), category=category, filename=filename)
    db.add(db_file)

    await db.commit()
    await db.refresh(db_file)

    return db_file


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if await get_max_lvl(db, user) < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только админы могут удалять файлы.",
        )

    file = await db.get(FileModel, file_id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден в БД."
        )

    filename = file.file_url.split("/")[-1]
    await file_delete(filename)

    await db.delete(file)
    await db.commit()

    return "Файл был успешно удалён."

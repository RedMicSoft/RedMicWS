import os
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.projects.schemas import ProjectResponse
from app.projects.models import Project as ProjectModel
from app.users.models import User as UserModel
from sqlalchemy.orm import selectinload
from sqlalchemy import select

MEDIA_DIR = Path(__file__).resolve().parent.parent.parent / "media"
PROJECT_IMAGES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "media" / "project_images"
)
PROJECT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


async def delete_project_cover(db_path: str) -> None:
    image_path = PROJECT_IMAGES_DIR / db_path.split("/")[-1]
    if image_path.exists():
        image_path.unlink()


async def upd_project_cover(image: UploadFile, exist_image: str | None):
    if not image.filename.endswith(ALLOWED_IMG_EXT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимый формат файла."
        )
    if exist_image:
        image_path = PROJECT_IMAGES_DIR / exist_image.split("/")[-1]
        if image_path.exists():
            image_path.unlink()
    content = await image.read()
    filename = f"{uuid.uuid4()}.{image.filename.split('.')[-1]}"
    file_path = PROJECT_IMAGES_DIR / filename
    file_path.write_bytes(content)

    return f"/media/project_images/{filename}"


async def get_db_project(project_id: int, db: AsyncSession):
    db_project = await db.scalar(
        select(ProjectModel)
        .options(
            selectinload(ProjectModel.links),
            selectinload(ProjectModel.participants),
            selectinload(ProjectModel.series_list),
            selectinload(ProjectModel.roles),
            selectinload(ProjectModel.curator).options(
                selectinload(UserModel.contacts), selectinload(UserModel.team_roles)
            ),
        )
        .where(ProjectModel.project_id == project_id)
    )

    if not db_project:
        raise HTTPException(status_code=404, detail="Проект не найден.")

    project = ProjectResponse.model_validate(db_project)

    return project


async def save_role_image(image: UploadFile):
    if not image.filename.endswith(ALLOWED_IMG_EXT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимый формат."
        )

    role_images_dir = MEDIA_DIR / "project_roles"
    role_images_dir.mkdir(parents=True, exist_ok=True)

    content = await image.read()
    filename = f"{uuid.uuid4()}.{image.filename.split('.')[-1]}"
    file_path = role_images_dir / filename
    file_path.write_bytes(content)

    return f"/media/project_roles/{filename}"


def delete_role_image(db_url: str):
    filename = db_url.split("/")[-1]
    path_to_delete = MEDIA_DIR / "project_roles" / filename

    if not path_to_delete.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден на сервере."
        )

    path_to_delete.unlink()

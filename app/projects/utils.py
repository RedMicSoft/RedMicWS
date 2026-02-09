from pathlib import Path
from fastapi import UploadFile, HTTPException, status
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.projects.schemas import ProjectResponse
from app.projects.models import Project as ProjectModel
from app.users.models import User as UserModel
from sqlalchemy.orm import selectinload
from sqlalchemy import select


PROJECT_IMAGES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "media" / "project_images"
)
PROJECT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


async def upd_project_cover(image: UploadFile, exist_image: str | None):
    if not image.filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
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

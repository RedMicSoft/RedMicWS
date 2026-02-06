from pathlib import Path
from fastapi import UploadFile, HTTPException, status
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_IMAGES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "media" / "project_images"
)
PROJECT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


async def save_project_image(image: UploadFile):
    if not image.filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимый формат файла."
        )
    content = await image.read()
    filename = f"{uuid.uuid4()}.{image.filename.split('.')[-1]}"
    file_path = PROJECT_IMAGES_DIR / filename
    file_path.write_bytes(content)

    return f"/media/project_images/{filename}"

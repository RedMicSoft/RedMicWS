from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media"


async def save_demo(demo: UploadFile) -> str:
    if not demo.filename.endswith(".mp4"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Демо должно быть в формате .mp4"
        )

    content = await demo.read()
    file_path = MEDIA_ROOT / "demo" / demo.filename
    file_path.write_bytes(content)

    return f"/media/demo/{demo.filename}"

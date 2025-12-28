from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media"


async def save_srt(srt: UploadFile) -> str:
    if not srt.filename.endswith(".srt"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл должен быть .srt")

    content = await srt.read()
    file_path = MEDIA_ROOT / "srt" / srt.filename
    file_path.write_bytes(content)

    return f"/media/srt/{srt.filename}"

from pathlib import Path
from fastapi import UploadFile
from sqlalchemy import select
from starlette.staticfiles import StaticFiles
import uuid

from app.files.models import FileModel
from app.database import async_session_maker

FILES_DIR = Path(__file__).resolve().parent.parent.parent / "team_files"
FILES_DIR.mkdir(parents=True, exist_ok=True)


async def save_file(file: UploadFile):
    content = await file.read()

    prev_filename = file.filename
    filename = f'{uuid.uuid4()}.{file.filename.split(".")[-1]}'
    file_path = FILES_DIR / filename
    file_path.write_bytes(content)

    return {"file_url": f"/team_files/{filename}", "prev_filename": prev_filename}


class CustomStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        print(f"Запрошен файл: {path}")
        try:
            response = await super().get_response(path, scope)
        except Exception as e:
            from starlette.responses import Response

            return Response("Файл не найден.", status_code=404)

        full_db_path = f"/team_files/{path}"
        async with async_session_maker() as db:
            file = await db.scalar(
                select(FileModel).where(FileModel.file_url == full_db_path)
            )
        if hasattr(response, "headers"):
            response.headers["Content-Disposition"] = (
                f'attachment; filename="{file.prev_filename}"'
            )

        print(f"Успешно, новое имя файла: {file.prev_filename}")
        return response

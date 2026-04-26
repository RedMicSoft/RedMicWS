from abc import abstractmethod

from fastapi import HTTPException, status
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy import select
from starlette.staticfiles import StaticFiles
import uuid
import os
import shutil
from starlette.concurrency import run_in_threadpool
from urllib.parse import quote

from app.files.models import FileModel
from app.roles.models import Record
from app.database import async_session_maker
from app.series.models import Material

FILES_DIR = Path(__file__).resolve().parent.parent.parent / "team_files"
FILES_DIR.mkdir(parents=True, exist_ok=True)


async def save_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Файл не выбран."
        )

    prev_filename = file.filename
    filename = f'{uuid.uuid4()}.{file.filename.split(".")[-1]}'
    file_path = FILES_DIR / filename
    with file_path.open("wb") as buffer:
        await run_in_threadpool(shutil.copyfileobj, file.file, buffer)

    return {"file_url": f"/team_files/{filename}", "prev_filename": prev_filename}


class CustomStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        print(f"Запрошен файл: {path}")
        try:
            response = await super().get_response(path, scope)
        except Exception as e:
            from starlette.responses import Response

            return Response("Файл не найден.", status_code=404)

        prev_filename = await self._get_original_file_name(path)
        if hasattr(response, "headers"):
            encoded_filename = quote(prev_filename)
            response.headers["Content-Disposition"] = (
                f"attachment; filename*=utf-8''{encoded_filename}"
            )

        print(f"Успешно, новое имя файла: {prev_filename}")
        return response

    @abstractmethod
    async def _get_original_file_name(self, path: str) -> str:
        pass


class TeamStaticFiles(CustomStaticFiles):
    async def _get_original_file_name(self, path: str) -> str:
        full_db_path = f"/team_files/{path}"
        async with async_session_maker() as db:
            file = await db.scalar(
                select(FileModel).where(FileModel.file_url == full_db_path)
            )
            material = await db.scalar(
                select(Material).where(Material.material_link == full_db_path)
            )
        return (
            file.prev_filename
            if file and file.prev_filename
            else (
                material.material_prev_title
                if material and material.material_prev_title
                else Path(path).name
            )
        )


class SubsStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except Exception:
            from starlette.responses import Response

            return Response("Файл не найден.", status_code=404)

        if hasattr(response, "headers"):
            filename = Path(path).name
            encoded_filename = quote(filename)
            response.headers["Content-Disposition"] = (
                f"attachment; filename*=utf-8''{encoded_filename}"
            )

        return response


class RecordsStaticFiles(CustomStaticFiles):
    async def _get_original_file_name(self, path: str) -> str:
        full_db_path = f"/records/{path}"
        async with async_session_maker() as db:
            file = await db.scalar(
                select(Record).where(Record.record_url == full_db_path)
            )
        return (
            file.record_prev_title
            if file and file.record_prev_title
            else Path(path).name
        )


async def file_delete(filename: str):
    file_to_delete = FILES_DIR / filename

    if not file_to_delete.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден в директории."
        )

    os.remove(file_to_delete)

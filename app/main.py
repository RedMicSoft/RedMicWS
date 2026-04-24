from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Request, Response

from app.files.utils import (
    CustomStaticFiles,
    RecordsStaticFiles,
    SubsStaticFiles,
    TeamStaticFiles,
)
from app.users.utils import scheduler
from contextlib import asynccontextmanager
from typing import AsyncGenerator

DELETED_USER_ID = -1  # Здесь айди удаленного пользователя в БД


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print("Запуск сервера...")
    scheduler.start()
    print(DELETED_USER_ID)
    yield

    print("Остановка сервера...")


app = FastAPI(lifespan=lifespan)

@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "https://redmic-team.com",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        },
    )

app.mount(
    "/media",
    StaticFiles(directory="media"),
    name="media",
)
app.mount(
    "/team_files",
    TeamStaticFiles(directory="team_files"),
    name="team_files",
)
app.mount(
    "/subs",
    SubsStaticFiles(directory="subs"),
    name="subs",
)
app.mount(
    "/records",
    RecordsStaticFiles(directory="records"),
    name="records",
)


@app.get("/")
async def root():
    return {"message": "Welcome!"}


# test com 3

from app.users.routes import router as user_router
from app.levels.routes import router as levels_router
from app.projects.routes import router as projects_router
from app.series.routes import router as series_router
from app.files.routes import router as files_router, CustomStaticFiles
from app.links.routes import router as links_router

app.include_router(user_router)
app.include_router(levels_router)
app.include_router(projects_router)
app.include_router(series_router)
app.include_router(files_router)
app.include_router(links_router)


origins = [
    "https://redmic-team.com",
    "https://redmic-workspace-test.ru",
    "http://localhost:35565"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Or replace "*" with your frontend's origin if known
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

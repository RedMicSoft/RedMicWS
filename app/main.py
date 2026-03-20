from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.files.utils import CustomStaticFiles
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

app.mount(
    "/media",
    StaticFiles(directory="media"),
    name="media",
)
app.mount(
    "/team_files",
    CustomStaticFiles(directory="team_files"),
    name="team_files",
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
    "https://redmic-workspace-test.ru"
    # можно добавить "http://localhost:3000" для локальной разработки
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Or replace "*" with your frontend's origin if known
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

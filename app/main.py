from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount(
    "/media",
    StaticFiles(directory="media"),
    name="media",
)


@app.get("/")
async def root():
    return {"message": "Welcome!"}

#test com 3

from app.users import router as user_router
from app.profiles import router as profiles_router
from app.levels.routes import router as levels_router
from app.projects.routes import router as projects_router
from app.series.routes import router as series_router

app.include_router(user_router)
app.include_router(profiles_router)
app.include_router(levels_router)
app.include_router(projects_router)
app.include_router(series_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or replace "*" with your frontend's origin if known
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Welcome!"}


from app.users import router as user_router
from app.profiles import router as profiles_router
from app.levels import router as levels_router

app.include_router(user_router)
app.include_router(profiles_router)
app.include_router(levels_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or replace "*" with your frontend's origin if known
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

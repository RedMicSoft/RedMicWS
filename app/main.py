from fastapi import FastAPI
from app.users import router as user_router

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Welcome!"}


app.include_router(user_router)

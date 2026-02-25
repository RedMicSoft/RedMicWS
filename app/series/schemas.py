from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from ..users.schemas import UserResponse
from sqlalchemy import null, Null


class SeriesResponse(BaseModel):
    id: int
    title: str

    model_config = ConfigDict(from_attributes=True)


class SeriesCreate(BaseModel):
    title: str

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from ..users.schemas import UserResponse


class SeriesResponse(BaseModel):
    id: int
    title: str

    model_config = ConfigDict(from_attributes=True)


class SeriesCreate(BaseModel):
    title: str
    project_id: int

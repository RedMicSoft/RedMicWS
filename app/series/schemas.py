from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from ..users.schemas import UserResponse
from sqlalchemy import null, Null


class SeriesParticipant(BaseModel):
    nickname: str
    id: int | None
    avatar_url: str | None


class SeriesListResponse(BaseModel):
    id: int
    project_id: int
    title: str
    state: str
    dub_progress: str
    participants: list[SeriesParticipant]

    model_config = ConfigDict(from_attributes=True)


class SeriesCreate(BaseModel):
    title: str

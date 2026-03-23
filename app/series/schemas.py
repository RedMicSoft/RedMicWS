from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from ..users.schemas import UserResponse
from sqlalchemy import null, Null


class SeriesParticipant(BaseModel):
    nickname: str
    id: int | None
    avatar_url: str | None


class ProjectSeriesResponse(BaseModel):
    id: int
    project_id: int
    title: str
    state: str

    model_config = ConfigDict(from_attributes=True)


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
    stage_time: int


class SeriesCreateProjectResponse(BaseModel):
    project_id: int
    title: str
    curator_id: int


class SeriesCreateSeriesResponse(BaseModel):
    id: int
    project: SeriesCreateProjectResponse
    title: str
    first_deadline: date
    second_deadline: date
    exp_publish_date: date
    note: str
    state: str
    ass_url: str | None

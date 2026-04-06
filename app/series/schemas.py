from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime, date
from ..users.schemas import UserResponse
from sqlalchemy import null, Null
from .models import SeriesState


class SeriesParticipant(BaseModel):
    nickname: str
    user_id: int | None
    avatar_url: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class SeriesCreateSeriesResponse(BaseModel):
    id: int
    project: SeriesCreateProjectResponse | None = None
    title: str
    start_date: date
    first_deadline: date
    second_deadline: date
    exp_publish_date: date
    note: str
    state: str
    ass_url: None = None
    materials: list[Any] | None = None
    links: list[Any] = None
    no_actors: dict[str, SeriesParticipant | None] | None = None
    roles: list[Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class UserWorkSeriaInfo(BaseModel):
    seria_id: int
    seria_title: str
    state: str


class UserWorkProjectInfo(BaseModel):
    project_id: int
    project_title: str


class UserWorkRoleInfo(BaseModel):
    role_name: str
    state: str


class UserWorkItem(BaseModel):
    seria: UserWorkSeriaInfo
    project: UserWorkProjectInfo
    work_type: str
    role_is_ready: bool
    subs: bool
    role: UserWorkRoleInfo | None


class SeriesDataUpdate(BaseModel):
    seria_title: Optional[str] = None
    start_date: Optional[date] = None
    first_stage_date: Optional[date] = None
    second_stage_date: Optional[date] = None
    publication_date: Optional[date] = None
    note: Optional[str] = None
    state: Optional[SeriesState] = None

    @field_validator(
        "start_date",
        "first_stage_date",
        "second_stage_date",
        "publication_date",
        mode="before",
    )
    @classmethod
    def parse_date(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return datetime.strptime(v, "%d.%m.%y").date()
            except ValueError:
                raise ValueError("Дата должна быть в формате ДД.ММ.ГГ")
        return v


class SeriesDataResponse(BaseModel):
    seria_title: str
    start_date: date
    first_stage_date: date
    second_stage_date: date
    publication_date: date
    note: str | None
    state: str


class SeriesMaterialsResponse(BaseModel):
    id: int
    material_title: str
    material_prev_title: str
    material_link: str


class SeriesResponse(BaseModel):
    id: int
    project: SeriesCreateProjectResponse
    title: str
    start_date: date
    first_deadline: date
    second_deadline: date
    exp_publish_date: date
    note: str
    state: str
    materials: list[SeriesMaterialsResponse] = Field(default_factory=list)

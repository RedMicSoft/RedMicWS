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


class SeriesNoActorsUpdate(BaseModel):
    curator: int | None = None
    sound_engineer: int | None = None
    raw_sound_engineer: int | None = None
    director: int | None = None
    timer: int | None = None
    subtitler: int | None = None


class SeriesNoActorsResponse(BaseModel):
    curator: SeriesParticipant | None
    sound_engineer: SeriesParticipant | None
    raw_sound_engineer: SeriesParticipant | None
    director: SeriesParticipant | None
    timer: SeriesParticipant | None
    subtitler: SeriesParticipant | None


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


class MaterialCreateResponse(BaseModel):
    id: int
    material_title: str
    material_link: str

    model_config = ConfigDict(from_attributes=True)


class SeriesLinkCreate(BaseModel):
    link_url: str
    link_title: str


class SeriesLinkResponse(BaseModel):
    id: int
    link_url: str
    link_title: str

    model_config = ConfigDict(from_attributes=True)


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


# --- Schemas for PUT /{seria_id}/subs ---

class AssFixItemResponse(BaseModel):
    fix_id: int
    fix_note: str

    model_config = ConfigDict(from_attributes=True)


class AssFileSubsResponse(BaseModel):
    ass_file_url: str
    ass_fixes: list[AssFixItemResponse]


class ActorSubsResponse(BaseModel):
    user_id: int
    nickname: str
    avatar_url: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class FixSubsResponse(BaseModel):
    id: int
    phrase: int
    note: str
    ready: bool

    model_config = ConfigDict(from_attributes=True)


class RecordSubsResponse(BaseModel):
    id: int
    record_title: str
    record_note: str | None
    record_url: str

    model_config = ConfigDict(from_attributes=True)


class RoleSubsResponse(BaseModel):
    id: int
    role_name: str
    actor: ActorSubsResponse | None
    fixes: list[FixSubsResponse]
    note: str | None
    checked: bool
    timed: bool
    state: str
    subtitle: str
    records: list[RecordSubsResponse]


class SubsUpdateResponse(BaseModel):
    ass_file: AssFileSubsResponse
    roles: list[RoleSubsResponse]


class AssFixCreateRequest(BaseModel):
    fix_note: str


class AssFixCreateResponse(BaseModel):
    fix_id: int
    fix_note: str

    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    role_name: str


class ActorCreateResponse(BaseModel):
    id: int
    nickname: str
    avatar_url: str | None


class RoleCreateResponse(BaseModel):
    id: int
    role_name: str
    actor: ActorCreateResponse | None
    fixes: None = None
    note: str
    checked: bool
    timed: bool
    state: str
    subtitle: str | None
    records: None = None


class RoleActorUpdate(BaseModel):
    actor_id: int | None


class RoleActorResponse(BaseModel):
    user_id: int | None
    nickname: str | None
    avatar_url: str | None


class RoleStateUpdate(BaseModel):
    checked: bool | None = None
    timed: bool | None = None


class RoleStateResponse(BaseModel):
    checked: bool
    timed: bool
    state: str


class RoleSubtitleFixResponse(BaseModel):
    id: int
    phrase: int
    note: str
    ready: bool

    model_config = ConfigDict(from_attributes=True)


class RoleSubtitleResponse(BaseModel):
    subtitle: str
    state: str
    checked: bool
    fixes: list[RoleSubtitleFixResponse]

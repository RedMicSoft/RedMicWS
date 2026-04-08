from fastapi import Form
from datetime import date
from typing import Literal, Annotated
from pydantic import BaseModel, Field, ConfigDict
from app.users.schemas import UsersResponse
from app.series.schemas import SeriesListResponse, ProjectSeriesResponse

voice_types = Literal["закадр", "рекаст", "дубляж"]
status_list = Literal["подготовка", "в работе", "завершён", "приостановлен", "закрыт"]


class ProjectLinkCreate(BaseModel):
    title: str
    url: str


class ProjectLinkResponse(BaseModel):
    id: int
    title: str
    url: str

    model_config = ConfigDict(from_attributes=True)


class ParticipantsResponse(BaseModel):
    user_id: int
    nickname: str
    avatar_url: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ParticipantsUpdate(BaseModel):
    user_id: int


class RoleResponse(BaseModel):
    role_id: int
    role_title: str
    user: UsersResponse
    image_url: str | None

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    role_title: str
    user_id: int

    @classmethod
    def as_form(
        cls,
        role_title: Annotated[str, Form(...)],
        user_id: Annotated[int, Form(...)],
    ) -> "RoleCreate":
        return cls(
            role_title=role_title,
            user_id=user_id,
        )


class ProjectResponse(BaseModel):
    project_id: int
    title: str
    created_at: date
    curator: UsersResponse
    type: str
    status: str
    series_list: list[ProjectSeriesResponse] | None
    links: list[ProjectLinkResponse] | None
    participants: list[ParticipantsResponse] | None
    roles: list[RoleResponse] | None
    image_url: str | None
    description: str | None
    way: str | None

    model_config = ConfigDict(from_attributes=True)


class ProjectParticipantsResponse(BaseModel):
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class ProjectsResponse(BaseModel):
    project_id: int
    title: str
    status: str
    way: str | None
    image_url: str | None
    participants: list[int] | None

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    title: str
    type: voice_types = Field(
        examples=["закадр", "рекаст", "дубляж"], description="тип озвучки"
    )  # проверить описание в сваггере
    created_at: date
    curator_id: int
    status: status_list = Field(
        examples=["подготовка", "в работе", "завершён", "приостановлен", "закрыт"],
        default="подготовка",
    )  # default = подготовка
    description: str | None
    way: str | None

    @classmethod
    def as_form(
        cls,
        title: Annotated[str, Form(...)],
        type: Annotated[voice_types, Form(...)],
        created_at: Annotated[date, Form(...)],
        curator_id: Annotated[int, Form(...)],
        description: Annotated[str | None, Form(...)],
        way: Annotated[str | None, Form(...)],
        status: Annotated[status_list, Form(...)] = "подготовка",
    ) -> "ProjectCreate":
        return cls(
            title=title,
            type=type,
            created_at=created_at,
            curator_id=curator_id,
            status=status,
            description=description,
            way=way,
        )


class ProjectTitleUpdate(BaseModel):
    title: str


class ProjectStatusUpdate(BaseModel):
    status: status_list


class ProjectCuratorUpdate(BaseModel):
    curator_id: int


class ProjectParticipantCreate(BaseModel):
    participant_id: int


class ProjectDescriptionUpdate(BaseModel):
    description: str

class ProjectWayUpdate(BaseModel):
    way: str


class ProjectTypeUpdate(BaseModel):
    type: voice_types

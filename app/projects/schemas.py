from fastapi import Form
from datetime import date
from typing import Literal, Annotated
from pydantic import BaseModel, Field, ConfigDict
from app.users.schemas import UsersResponse
from app.series.schemas import SeriesResponse

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

    model_config = ConfigDict(from_attributes=True)


class ParticipantsUpdate(BaseModel):
    user_id: int


class ProjectResponse(BaseModel):
    title: str
    created_at: date
    curator: UsersResponse
    type: str
    status: str
    series_list: list[SeriesResponse] | None
    links: list[ProjectLinkResponse] | None
    participants: list[ParticipantsResponse] | None
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class ProjectsResponse(BaseModel):
    project_id: int
    title: str
    status: str
    image_url: str

    ConfigDict(from_attributes=True)


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

    @classmethod
    def as_form(
        cls,
        title: Annotated[str, Form(...)],
        type: Annotated[voice_types, Form(...)],
        created_at: Annotated[date, Form(...)],
        curator_id: Annotated[int, Form(...)],
        description: Annotated[str, Form(...)],
        status: Annotated[status_list, Form(...)] = "подготовка",
    ) -> "ProjectCreate":
        return cls(
            title=title,
            type=type,
            created_at=created_at,
            curator_id=curator_id,
            status=status,
            description=description,
        )

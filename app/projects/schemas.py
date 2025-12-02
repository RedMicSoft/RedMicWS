from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

voice_types = Literal["закадр", "рекаст", "дубляж"]
status_list = Literal["подготовка", "в работе", "завершён", "приостановлен", "закрыт"]


class ProjectResponse(BaseModel):
    project_id: int
    title: str
    type: str
    curator: str
    image_url: str
    created_at: date
    is_active: bool
    status: str

    ConfigDict(from_attributes=True)


class ProjectLinkCreate(BaseModel):
    title: str
    url: str


class ProjectCreate(BaseModel):
    title: str
    type: voice_types = Field(
        examples=["закадр", "рекаст", "дубляж"], description="тип озвучки"
    )  # проверить описание в сваггере
    image_url: str | None
    created_at: date
    curator: str
    participants: list[str]
    links: list[ProjectLinkCreate]
    status: status_list = Field(
        examples=["подготовка", "в работе", "завершён", "приостановлен", "закрыт"]
    )

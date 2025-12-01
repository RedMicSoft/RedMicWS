from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

voice_types = Literal["закадр", "рекаст", "дубляж"]


class ProjectResponse(BaseModel):
    project_id: int
    title: str
    type: str
    curator: int
    image_url: str
    created_at: date
    is_active: bool

    ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    title: str
    type: voice_types = Field(
        examples=["закадр", "рекаст", "дубляж"], description="тип озвучки"
    )  # проверить описание в сваггере
    image_url: str | None
    created_at: date
    is_active: bool

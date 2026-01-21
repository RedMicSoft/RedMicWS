from typing import Annotated

from pydantic import Field, BaseModel, ConfigDict
from fastapi import Form


class RoleCreate(BaseModel):
    profile_id: int
    name: str

    @classmethod
    def as_form(
        cls,
        user_id: Annotated[int, Form(...)],
        name: Annotated[str, Form(...)],
    ) -> "RoleCreate":
        return cls(profile_id=user_id, name=name)


class RoleResponse(BaseModel):
    role_id: int
    profile_id: int
    project_id: int
    srt: str
    name: str
    result_url: str
    is_active: bool


class RoleHistory(BaseModel):
    project_name: str
    role_name: str
    image_url: str

    model_config = ConfigDict(from_attributes=True)

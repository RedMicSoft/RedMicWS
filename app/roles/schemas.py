from typing import Annotated

from pydantic import Field, BaseModel
from fastapi import Form


class RoleCreate(BaseModel):
    profile_id: int
    name: str

    @classmethod
    def as_form(
        cls,
        profile_id: Annotated[int, Form(...)],
        name: Annotated[str, Form(...)],
    ) -> "RoleCreate":
        return cls(profile_id=profile_id, name=name)


class RoleResponse(BaseModel):
    role_id: int
    profile_id: int
    project_id: int
    srt: str
    name: str
    result_url: str
    is_active: bool

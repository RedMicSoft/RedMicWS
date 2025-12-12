from pydantic import Field, BaseModel


class RoleCreate(BaseModel):
    user_id: int
    srt: str
    name: str
    result_url: str | None = Field(default=None)


class RoleResponse(BaseModel):
    role_id: int
    user_id: int
    srt: str
    name: str
    result_url: str
    is_active: bool

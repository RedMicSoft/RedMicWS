from pydantic import BaseModel, Field, ConfigDict


class LevelCreate(BaseModel):
    role_name: str = Field(...)
    access_level: int = Field(..., ge=1, le=4)


class LevelResponse(BaseModel):
    level_id: int
    role_name: str
    access_level: int
    is_active: bool

    ConfigDict(from_attributes=True)

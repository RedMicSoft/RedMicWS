from pydantic import BaseModel, Field, ConfigDict


class LevelCreate(BaseModel):
    role_name: str = Field(...)
    access_level: int = Field(..., ge=1, le=3)


class LevelResponse(BaseModel):
    level_id: int
    role_name: str
    access_level: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

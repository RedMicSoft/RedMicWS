from datetime import date, datetime

from pydantic import BaseModel, Field, ConfigDict


class ProfileCreate(BaseModel):
    avatar: str | None = Field(default=None)
    age: int | None = Field(default=None)
    birth_date: date | None = Field(default=None)


class ProfileResponse(BaseModel):
    profile_id: int
    user_id: int
    avatar: str | None
    age: int | None
    birth_date: date | None
    registered_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

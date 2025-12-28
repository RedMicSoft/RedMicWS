from datetime import date, datetime

from pydantic import BaseModel, Field, ConfigDict


class ProfileCreate(BaseModel):
    avatar: str | None = Field(default=None)
    birth_date: date | None = Field(default=None)
    description: str | None = Field(default=None)


class ProfileResponse(BaseModel):
    profile_id: int
    user_id: int
    avatar: str | None
    age: int | None
    birth_date: date | None
    registered_at: datetime
    updated_at: datetime
    is_active: bool
    description: str | None
    rest_start: datetime | None
    rest_end: datetime | None
    demo_url: str | None

    model_config = ConfigDict(from_attributes=True)

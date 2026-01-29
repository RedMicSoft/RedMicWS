from datetime import date, datetime
from pydantic import computed_field, BaseModel, Field, ConfigDict, EmailStr, Field
from dateutil.relativedelta import relativedelta
from typing import Optional

from app.levels.schemas import LevelResponse
from app.roles.schemas import RoleHistoryResponse


class ContactCreate(BaseModel):
    title: str
    link: str


class ContactResponse(BaseModel):
    title: str
    link: str

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """
    Схема создания для POST запросов.
    """

    nickname: str
    password: str
    join_date: date = Field(le=date.today())
    birth_date: date | None = Field(le=date.today())
    description: str | None
    contacts: list[ContactCreate]


class UserResponse(BaseModel):
    """
    Схема ответа для GET запросов.
    """

    user_id: int
    nickname: str
    birth_date: date | None
    join_date: date | None
    rest: dict | None
    contacts: list[ContactResponse]
    description: str | None
    demo_url: str | None
    avatar_url: str | None
    team_roles: list[LevelResponse]
    roles: list[RoleHistoryResponse] | None
    is_active: bool

    @computed_field
    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        return relativedelta(date.today(), self.birth_date).years

    model_config = ConfigDict(from_attributes=True)


class UsersResponse(BaseModel):
    user_id: int
    nickname: str
    birth_date: date | None
    contacts: list[ContactResponse]
    avatar_url: str | None
    team_roles: list[LevelResponse] = []
    is_active: bool

    @computed_field
    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        return relativedelta(date.today(), self.birth_date).years

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """
    Схема создания для PATCH запросов.
    """

    nickname: str | None = Field(default=None)
    join_date: Optional[date] = Field(default=None, le=date.today())
    birth_date: Optional[date] = Field(default=None, le=date.today())
    description: str | None = Field(default=None)
    contacts: list[ContactCreate] | None = Field(default=None)


class RestCreate(BaseModel):
    rest_start: date
    rest_end: date
    rest_reason: str

from datetime import date, datetime
from pydantic import computed_field, BaseModel, Field, ConfigDict, EmailStr, Field
from dateutil.relativedelta import relativedelta

from app.levels.schemas import LevelResponse
from app.roles.schemas import RoleHistory


class ContactCreate(BaseModel):
    title: str
    link: str


class ContactResponse(BaseModel):
    title: str
    link: str

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """
    Схема создания для POST/PUT запросов.
    """

    nickname: str
    password: str
    join_date: date
    birth_date: date | None
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
    roles: list[RoleHistory] | None
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
    team_roles: list[LevelResponse]
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
    Схема создания для POST/PUT запросов.
    """

    nickname: str
    join_date: date
    birth_date: date | None
    description: str | None
    contacts: list[ContactCreate]

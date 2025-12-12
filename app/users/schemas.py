from pydantic import BaseModel, Field, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """
    Схема создания для POST/PUT запросов.
    """

    nickname: str
    password: str


class UserResponse(BaseModel):
    """
    Схема ответа для GET запросов.
    """

    user_id: int
    nickname: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

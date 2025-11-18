from pydantic import BaseModel, Field, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """
    Схема создания для POST/PUT запросов.
    """

    email: EmailStr
    password: str
    access_level: int = Field(ge=1, le=3, description="Уровень доступа от 1 до 3")


class UserResponse(BaseModel):
    """
    Схема ответа для GET запросов.
    """

    user_id: int
    email: EmailStr
    hashed_password: str
    access_level: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

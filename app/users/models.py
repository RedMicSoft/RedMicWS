from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import String


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column()
    access_level: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

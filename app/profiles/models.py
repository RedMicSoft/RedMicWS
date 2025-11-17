from sqlalchemy import ForeignKey, Date
from sqlalchemy.orm import mapped_column, Mapped
from datetime import date, datetime, timezone

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    avatar_url: Mapped[str | None] = mapped_column()
    age: Mapped[int | None] = mapped_column()
    birth_date: Mapped[date | None] = mapped_column(Date)
    role: Mapped[str] = mapped_column()
    registered_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(default=True)

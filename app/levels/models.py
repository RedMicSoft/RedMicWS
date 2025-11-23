from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import String, ForeignKey


class Level(Base):
    __tablename__ = "levels"

    level_id: Mapped[int] = mapped_column(primary_key=True)
    role_name: Mapped[str] = mapped_column()
    access_level: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="levels",
        secondary="user_level",
    )


class UserLevel(Base):
    __tablename__ = "user_level"

    level_id: Mapped[int] = mapped_column(
        ForeignKey("levels.level_id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), primary_key=True)

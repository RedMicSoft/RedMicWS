from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import String, ForeignKey


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    profile: Mapped["Profile"] = relationship(
        "Profile",
        back_populates="user",
    )

    levels: Mapped[list["Level"]] = relationship(
        "Level",
        back_populates="users",
        secondary="user_level",
    )

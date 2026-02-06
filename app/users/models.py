from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import String, ForeignKey
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column()
    avatar_url: Mapped[str | None]
    birth_date: Mapped[date | None] = mapped_column()
    join_date: Mapped[date] = mapped_column()
    description: Mapped[str | None] = mapped_column()
    rest_start: Mapped[date | None] = mapped_column()
    rest_end: Mapped[date | None] = mapped_column()
    rest_reason: Mapped[str | None] = mapped_column()
    demo_url: Mapped[str | None] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    contacts: Mapped[list["Contacts"]] = relationship(
        "Contacts", back_populates="user", cascade="all, delete-orphan"
    )

    team_roles: Mapped[list["Level"]] = relationship(
        "Level",
        back_populates="users",
        secondary="user_level",
    )

    history: Mapped[list["RoleHistory"]] = relationship(
        "RoleHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="user",
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="participants", secondary="projects_users"
    )

    curator_projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="curator",
    )


class Contacts(Base):
    __tablename__ = "contacts"

    contact_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    title: Mapped[str] = mapped_column()
    link: Mapped[str] = mapped_column()

    user: Mapped["User"] = relationship(
        "User",
        back_populates="contacts",
    )

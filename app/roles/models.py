from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.database import Base, get_db

DELETED_USER_ID = -1


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(primary_key=True)
    role_name: Mapped[str] = mapped_column()
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"))
    note: Mapped[str | None] = mapped_column()
    checked: Mapped[bool] = mapped_column(default=False)
    timed: Mapped[bool] = mapped_column(default=False)
    state: Mapped[str] = mapped_column()
    srt_url: Mapped[str] = mapped_column()

    user: Mapped["User"] = relationship("User", back_populates="roles")

    fixes: Mapped["Fix"] = relationship(
        "Fix", back_populates="role", cascade="all, delete-orphan"
    )

    records: Mapped["Record"] = relationship(
        "Record", back_populates="role", cascade="all, delete-orphan"
    )

    series: Mapped["Series"] = relationship(
        "Series",
        back_populates="roles",
    )


class Fix(Base):
    __tablename__ = "fixes"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.role_id", ondelete="CASCADE")
    )
    phrase: Mapped[int] = mapped_column()
    note: Mapped[str] = mapped_column()
    ready: Mapped[bool] = mapped_column()

    role: Mapped["Role"] = relationship("Role", back_populates="fixes")


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.role_id", ondelete="CASCADE")
    )
    record_url: Mapped[str] = mapped_column()
    record_prev_title: Mapped[str] = mapped_column()

    role: Mapped["Role"] = relationship("Role", back_populates="records")


class RoleHistory(Base):
    __tablename__ = "role_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    project_name: Mapped[str] = mapped_column()
    role_name: Mapped[str] = mapped_column()
    image_url: Mapped[str | None] = mapped_column()

    user: Mapped["User"] = relationship(
        "User",
        back_populates="history",
    )

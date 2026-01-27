from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.database import Base, get_db
from app.main import DELETED_USER_ID


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    srt_url: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    result_url: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    series: Mapped[list["Series"]] = relationship(
        "Series",
        secondary="role_series",
        back_populates="roles",
    )

    user: Mapped[list["User"]] = relationship(
        "User",
        back_populates="roles",
    )


class RoleSeries(Base):
    __tablename__ = "role_series"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.role_id"),
        primary_key=True,
    )
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"), primary_key=True)


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

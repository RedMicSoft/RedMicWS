from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.profile_id"))
    srt_url: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    result_url: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    series: Mapped[list["Series"]] = relationship(
        "Series",
        secondary="role_series",
        back_populates="roles",
    )


class RoleSeries(Base):
    __tablename__ = "role_series"

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id"), primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"), primary_key=True)

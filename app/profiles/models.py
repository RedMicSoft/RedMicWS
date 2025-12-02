from sqlalchemy import ForeignKey, Date
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import date, datetime, timezone
from sqlalchemy import Text, True_

from app.database import Base
from app.projects import Project
from app.series import Series


class Profile(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), unique=True)
    avatar: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column()
    birth_date: Mapped[date | None] = mapped_column(Date)
    registered_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    # deprecated, потом удалю мб
    # projects: Mapped[list["Project"]] = relationship(
    #     "Project", back_populates="profiles", secondary="project_profiles"
    # )

    user: Mapped["User"] = relationship("User", back_populates="profile")

    series: Mapped[list["Series"]] = relationship(
        "Series", back_populates="profiles", secondary="profile_series"
    )


class ProfileSeries(Base):
    __tablename__ = "profile_series"

    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.profile_id"))
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"), primary_key=True)

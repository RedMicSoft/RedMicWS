from sqlalchemy import ForeignKey, Date
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import date, datetime, timezone
from sqlalchemy import Text, True_
from dateutil.relativedelta import relativedelta

from app.database import Base
from app.projects import Project
from app.series import Series


class Profile(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), unique=True)
    avatar: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)
    registered_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[Text | None] = mapped_column(Text)
    rest_start: Mapped[datetime | None] = mapped_column()
    rest_end: Mapped[datetime | None] = mapped_column()
    demo_url: Mapped[str | None] = mapped_column()

    user: Mapped["User"] = relationship("User", back_populates="profile")

    series: Mapped[list["Series"]] = relationship(
        "Series", back_populates="profiles", secondary="profile_series"
    )

    @property
    def age(self):
        if not self.birth_date:
            return None
        return relativedelta(date.today(), self.birth_date).years

    @property
    def rest(self):
        if self.rest_start:
            return relativedelta(date.today(), self.rest_end).days < 0
        return False


class ProfileSeries(Base):
    __tablename__ = "profile_series"

    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.profile_id"))
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"), primary_key=True)

from sqlalchemy import ForeignKey, Date
from datetime import datetime, date, timezone
from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"))
    title: Mapped[str] = mapped_column()
    start_date: Mapped[date] = mapped_column()
    first_deadline: Mapped[date] = mapped_column()
    second_deadline: Mapped[date] = mapped_column()
    exp_publish_date: Mapped[date] = mapped_column()
    raw_url: Mapped[str] = mapped_column()
    srt_url: Mapped[str] = mapped_column()
    result_url: Mapped[str] = mapped_column()
    curator: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    sound_engineer: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    sound_engineer_2: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    translator: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(
        Date, default=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    profiles: Mapped[list["Profile"]] = relationship(
        "Profile",
        back_populates="series",
        secondary="profile_series",
    )

from sqlalchemy import ForeignKey, Date, Text
from datetime import datetime, date, timezone
from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.main import DELETED_USER_ID


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
    ass_url: Mapped[str] = mapped_column()
    result_url: Mapped[str] = mapped_column()
    curator: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    sound_engineer: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    sound_engineer_minus: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    timer: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    translator: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    created_at: Mapped[datetime] = mapped_column(Date, default=lambda: datetime.now())
    is_active: Mapped[bool] = mapped_column(default=True)

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="series",
        secondary="role_series",
    )

from alembic.operations.toimpl import create_constraint
from sqlalchemy import ForeignKey, Date, Text, Enum as SAenum
from datetime import datetime, date, timezone
from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.sql import func
import enum


DELETED_USER_ID = -1


class SeriesState(enum.Enum):
    MATERIALS_PREPARATION = "подготовка материалов"
    VOICE_OVER = "озвучка"
    MIXING = "сведение"
    PUBLICATION = "публикация"
    COMPLETED = "завершено"


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"))
    title: Mapped[str] = mapped_column()
    start_date: Mapped[date] = mapped_column(server_default=func.current_date())
    first_deadline: Mapped[date] = mapped_column(server_default=func.current_date())
    second_deadline: Mapped[date] = mapped_column(server_default=func.current_date())
    exp_publish_date: Mapped[date] = mapped_column(server_default=func.current_date())
    ass_url: Mapped[str | None] = mapped_column()
    state: Mapped[str] = mapped_column(
        SAenum(SeriesState, native_enum=False),
        server_default=SeriesState.MATERIALS_PREPARATION.value,
    )

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

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="series",
        secondary="role_series",
    )

    project: Mapped["Project"] = relationship("Project", back_populates="series_list")

    materials: Mapped[list["Material"]] = relationship(
        "Material",
        back_populates="series",
        cascade="all, delete-orphan",
    )

    links: Mapped[list["SeriesLink"]] = relationship(
        "SeriesLink",
        back_populates="series",
        cascade="all, delete-orphan",
    )

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="series",
        cascade="all, delete-orphan",
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"))
    material_title: Mapped[str] = mapped_column()
    material_prev_title: Mapped[str] = mapped_column()
    material_link: Mapped[str] = mapped_column()

    series: Mapped["Series"] = relationship("Series", back_populates="materials")


class SeriesLink(Base):
    __tablename__ = "series_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"))
    link_title: Mapped[str] = mapped_column()
    link_url: Mapped[str] = mapped_column()

    series: Mapped["Series"] = relationship("Series", back_populates="links")

from sqlalchemy import ForeignKey, Date
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import date, datetime, timezone
from app.database import Base

DELETED_USER_ID = -1


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(unique=True)
    type: Mapped[str] = mapped_column()  # off-screen/recast/dub
    curator_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    image_url: Mapped[str | None] = mapped_column()
    created_at: Mapped[date] = mapped_column()
    status: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)

    links: Mapped[list["ProjectLink"]] = relationship(
        "ProjectLink",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    participants: Mapped[list["User"]] = relationship(
        "User",
        back_populates="projects",
        secondary="projects_users",
        cascade="all",
        passive_deletes=True,
    )

    curator: Mapped["User"] = relationship(
        "User",
        back_populates="curator_projects",
    )

    series_list: Mapped[list["Series"]] = relationship(
        "Series",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    roles: Mapped[list["ProjectRoleHistory"]] = relationship(
        "ProjectRoleHistory",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectLink(Base):
    __tablename__ = "project_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="links",
    )


class ProjectUser(Base):
    __tablename__ = "projects_users"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET DEFAULT"),
        primary_key=True,
        default=DELETED_USER_ID,
        server_default=str(DELETED_USER_ID),
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True
    )


class ProjectRoleHistory(Base):
    __tablename__ = "project_role_history"

    role_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE")
    )
    role_title: Mapped[str] = mapped_column()
    user_nickname: Mapped[str] = mapped_column()
    image_url: Mapped[str] = mapped_column()

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="roles",
    )

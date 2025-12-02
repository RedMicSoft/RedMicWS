from sqlalchemy import ForeignKey, Date
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import date, datetime, timezone
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(unique=True)
    type: Mapped[str] = mapped_column()  # off-screen/recast/dub
    curator: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    image_url: Mapped[str | None] = mapped_column()
    created_at: Mapped[date] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column()

    links: Mapped[list["ProjectLink"]] = relationship(
        "ProjectLink",
        back_populates="project",
    )

    # profiles: Mapped[list["Profile"]] = relationship(
    #     "Profile",
    #     back_populates="projects",
    #     secondary="project_profiles",
    # )

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="projects",
        secondary="projects_users",
    )


class ProjectLink(Base):
    __tablename__ = "project_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"))
    title: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="links",
    )


# deprecated
# class ProjectProfile(Base):
#     __tablename__ = "project_profiles"
#
#     project_id: Mapped[int] = mapped_column(
#         ForeignKey("projects.project_id"), primary_key=True
#     )
#     profile_id: Mapped[int] = mapped_column(
#         ForeignKey("profiles.profile_id"), primary_key=True
#     )


class ProjectUser(Base):
    __tablename__ = "projects_users"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id"), primary_key=True
    )

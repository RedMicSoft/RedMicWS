from app.database import Base

from sqlalchemy.orm import mapped_column, Mapped


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_title: Mapped[str] = mapped_column()
    link_url: Mapped[str] = mapped_column(unique=True)

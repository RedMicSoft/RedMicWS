from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FileModel(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column()
    file_url: Mapped[str] = mapped_column()
    category: Mapped[str] = mapped_column()
    prev_filename: Mapped[str | None] = mapped_column()

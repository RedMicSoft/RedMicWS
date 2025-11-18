from app.database import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import String
from app.profiles import Profile


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column()
    access_level: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    profile: Mapped["Profile"] = relationship(
        "Profile",
        back_populates="user",
    )

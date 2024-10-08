import datetime

from sqlalchemy import (
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped

from ..database import Base


class Birthday(Base):
    __tablename__ = "announcements_birthday"
    __table_args__ = (UniqueConstraint("guild_id", "user_id"),)

    birthday: Mapped[datetime.date]
    guild_id: Mapped[int]
    user_id: Mapped[int]

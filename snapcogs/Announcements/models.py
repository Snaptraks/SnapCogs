import datetime

from sqlalchemy import (
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

# class AnnouncementsBirthday(Base):
#     __tablename__ = "announcements_birthday"
#     __table_args__ = (UniqueConstraint("guild_id", "user_id"),)
#
#     id: Mapped[int] = mapped_column(Integer, primary_key=True)
#     birthday: Mapped[Optional[datetime.date]] = mapped_column(Date)
#     guild_id: Mapped[Optional[int]] = mapped_column(Integer)
#     user_id: Mapped[Optional[int]] = mapped_column(Integer)


class Birthday(Base):
    __tablename__ = "announcements_birthday"
    __table_args__ = (UniqueConstraint("guild_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    birthday: Mapped[datetime.date]
    guild_id: Mapped[int]
    user_id: Mapped[int]

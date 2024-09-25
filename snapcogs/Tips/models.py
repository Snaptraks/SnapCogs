from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Tip(Base):
    __tablename__ = "tips_tip"
    __table_args__ = (UniqueConstraint("guild_id", "name"),)

    author_id: Mapped[int]
    content: Mapped[str]
    created_at: Mapped[datetime]
    guild_id: Mapped[int]
    last_edited: Mapped[datetime]
    name: Mapped[str]
    uses: Mapped[int] = mapped_column(default=0)


@dataclass
class TipCounts:
    tips: int = 0
    uses: int = 0
    author_id: int | None = None

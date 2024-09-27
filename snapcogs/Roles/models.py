from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class View(Base):
    __tablename__ = "roles_view"

    guild_id: Mapped[int]
    message_id: Mapped[int] = mapped_column(unique=True)
    toggle: Mapped[bool]
    components: Mapped[list["Component"]] = relationship(cascade="all, delete-orphan")
    roles: Mapped[list["Role"]] = relationship(cascade="all, delete-orphan")


class Component(Base):
    __tablename__ = "roles_component"

    component_id: Mapped[str]
    name: Mapped[str]
    view_id: Mapped[int] = mapped_column(ForeignKey(View.id))


class Role(Base):
    __tablename__ = "roles_role"

    role_id: Mapped[int]
    view_id: Mapped[int] = mapped_column(ForeignKey(View.id))

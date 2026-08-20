import enum
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Persist each member's value; SQLAlchemy would otherwise store its name.

    Pass to ``Enum(..., values_callable=enum_values)`` so a member written as
    ``EDUCATION = "education"`` reaches the database as ``education`` rather
    than ``EDUCATION``.
    """
    return [member.value for member in enum_cls]


class Base(DeclarativeBase):
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

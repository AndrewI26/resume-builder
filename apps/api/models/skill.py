import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Skill(Base):
    """One labelled list of skills, e.g. ``Languages: Python, Go, SQL``.

    Items are stored as an array so their order is the array's order —
    reordering is a rewrite of the whole list. ``position`` orders the lists
    themselves against each other within a user's resume.
    """

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    items: Mapped[list[str]] = mapped_column(ARRAY(String(255)), default=list)

    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class PersonalInfo(Base):
    """A set of contact details for the top of a resume. Every field is optional.

    A user may have several — one per resume variant, say.
    """

    __tablename__ = "personal_info"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Each holds a `{"url": ..., "label": ...}` object; see schemas.link.Link.
    github: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    linkedin: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    portfolio: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

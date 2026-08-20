import uuid

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, enum_values
from enums import OperationType, SectionType


class SectionVersion(Base):
    """A copy of one section row as it stood at a point in time.

    ``section_id`` is deliberately not a foreign key: a delete is the case
    history exists for, so a snapshot has to outlive the row it describes.
    That leaves ``user_id`` as the only way to authorize a read, since for a
    deleted section there is no live row left to check ownership against.
    """

    __tablename__ = "section_versions"
    __table_args__ = (
        UniqueConstraint(
            "section_type",
            "section_id",
            "version",
            name="uq_section_versions_section_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    section_type: Mapped[SectionType] = mapped_column(
        SQLEnum(SectionType, name="section_version_type", values_callable=enum_values),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[OperationType] = mapped_column(
        SQLEnum(
            OperationType,
            name="section_version_operation",
            values_callable=enum_values,
        ),
        nullable=False,
    )

    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

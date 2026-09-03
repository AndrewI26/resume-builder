import uuid
from typing import Any

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, Json, enum_values
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
        # what makes ``seq`` an ordering rather than a hint
        UniqueConstraint("user_id", "seq", name="uq_section_versions_user_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    section_type: Mapped[SectionType] = mapped_column(
        SQLEnum(SectionType, name="section_version_type", values_callable=enum_values),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    # Two counters, because they answer different questions.
    #
    # ``version`` counts this record's own history. It is what decides whether
    # two sides of a sync disagree: an edit made against version 4 can only be
    # applied to something still at version 4.
    #
    # ``seq`` orders everything one user has ever changed. It is what lets a
    # sync ask for "everything since 812" and get it in the order it happened,
    # across every kind of record at once. Timestamps cannot do this — they tie,
    # and clocks move.
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    operation: Mapped[OperationType] = mapped_column(
        SQLEnum(
            OperationType,
            name="section_version_operation",
            values_callable=enum_values,
        ),
        nullable=False,
    )

    snapshot: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False)

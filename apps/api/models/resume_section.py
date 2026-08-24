import uuid

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, enum_values
from enums import ResumeSectionType


class ResumeSection(Base):
    """A section's membership of one resume, and its place within its block.

    ``section_id`` cannot be a foreign key because it points at one of four
    different tables depending on ``section_type``. Nothing at the database
    level therefore deletes these rows when the section they name goes away;
    the section routers clear them by hand on delete.

    ``position`` orders entries against others *of the same type* only. The
    order of the blocks themselves lives in ``Resume.section_order``.
    """

    __tablename__ = "resume_sections"
    __table_args__ = (
        UniqueConstraint(
            "resume_id",
            "section_type",
            "section_id",
            name="uq_resume_sections_resume_section",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )

    section_type: Mapped[ResumeSectionType] = mapped_column(
        SQLEnum(
            ResumeSectionType, name="resume_section_type", values_callable=enum_values
        ),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

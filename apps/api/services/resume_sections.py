"""Membership bookkeeping for the sections a resume lists.

``resume_sections.section_id`` points at one of four tables, so it cannot be a
foreign key and the database will not cascade a section's deletion into the
resumes that referenced it. Deleting a section therefore has to call
``detach_section`` explicitly.
"""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from enums import ResumeSectionType
from models.resume_section import ResumeSection


def detach_section(
    db: Session, section_type: ResumeSectionType, section_id: UUID
) -> None:
    """Drop a deleted section from every resume that listed it."""
    db.execute(
        delete(ResumeSection).where(
            ResumeSection.section_type == section_type,
            ResumeSection.section_id == section_id,
        )
    )

"""Resolving a resume's rows into the shape a renderer wants.

This moved out of the router because the PDF worker needs it too, and the
worker has no request to hang a dependency off — it is handed a resume id and
nothing else.
"""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from enums import ResumeSectionType
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.resume_section import ResumeSection
from models.skill import Skill
from models.user import User
from schemas.education import EducationRead
from schemas.personal_info import PersonalInfoRead
from schemas.resume import (
    EducationBlock,
    ExperienceBlock,
    ProjectBlock,
    ResumeDocument,
    SectionBlock,
    SkillBlock,
)
from schemas.skill import SkillRead
from services.bullet_points import bullet_points_by_id
from services.sections import expirence_to_read, project_to_read

# the table each section type's ids live in. ``resume_sections`` is polymorphic
# by hand, so every lookup starts here.
SECTION_MODELS: dict[ResumeSectionType, Any] = {
    ResumeSectionType.EDUCATION: Education,
    ResumeSectionType.EXPERIENCE: Expirence,
    ResumeSectionType.PROJECT: Project,
    ResumeSectionType.SKILL: Skill,
}


def section_ids_for(
    db: Session, resume_id: UUID
) -> dict[ResumeSectionType, list[UUID]]:
    """A resume's membership list, grouped by type and in position order.

    ``position`` orders entries against others of the same type only, so the
    grouping is what the ordering is actually about.
    """
    stmt = (
        select(ResumeSection)
        .where(ResumeSection.resume_id == resume_id)
        .order_by(ResumeSection.position, ResumeSection.created_at)
    )

    ids_by_type: dict[ResumeSectionType, list[UUID]] = defaultdict(list)
    for row in db.scalars(stmt):
        ids_by_type[row.section_type].append(row.section_id)

    return ids_by_type


def _ordered(rows: Sequence[Any], ids: Sequence[UUID]) -> list[Any]:
    """Put fetched rows back into the order their ids were listed in."""
    by_id = {row.id: row for row in rows}
    return [by_id[section_id] for section_id in ids if section_id in by_id]


def build_block(
    db: Session, user_id: UUID, section_type: ResumeSectionType, ids: list[UUID]
) -> SectionBlock:
    model = SECTION_MODELS[section_type]
    stmt = select(model).where(model.id.in_(set(ids)), model.user_id == user_id)
    rows = _ordered(db.scalars(stmt).all(), ids)

    if section_type is ResumeSectionType.EDUCATION:
        return EducationBlock(items=[EducationRead.model_validate(row) for row in rows])

    if section_type is ResumeSectionType.SKILL:
        return SkillBlock(items=[SkillRead.model_validate(row) for row in rows])

    by_id = bullet_points_by_id(
        db, [bullet_id for row in rows for bullet_id in row.bullet_points]
    )

    if section_type is ResumeSectionType.EXPERIENCE:
        return ExperienceBlock(items=[expirence_to_read(row, by_id) for row in rows])

    return ProjectBlock(items=[project_to_read(row, by_id) for row in rows])


def build_resume_document(
    db: Session,
    resume: Resume,
    ids_by_type: dict[ResumeSectionType, list[UUID]] | None = None,
) -> ResumeDocument:
    """The whole resume, resolved and ordered.

    Bullet points are hydrated, blocks arrive in ``section_order`` and empty
    ones are dropped, so a caller can walk this straight into a template.

    ``ids_by_type`` is accepted so a request that already resolved the
    membership through a dependency does not query for it twice.
    """
    if ids_by_type is None:
        ids_by_type = section_ids_for(db, resume.id)

    personal_info: PersonalInfoRead | None = None
    if resume.personal_info_id is not None:
        stmt = select(PersonalInfo).where(
            PersonalInfo.id == resume.personal_info_id,
            PersonalInfo.user_id == resume.user_id,
        )
        row = db.scalars(stmt).one_or_none()
        if row is not None:
            personal_info = PersonalInfoRead.model_validate(row)

    blocks: list[SectionBlock] = []
    for value in resume.section_order:
        ids = ids_by_type.get(ResumeSectionType(value), [])
        if not ids:
            continue

        block = build_block(db, resume.user_id, ResumeSectionType(value), ids)
        # a section whose rows were all deleted leaves stale ids behind; an
        # empty block would render as a bare heading, so drop it
        if block.items:
            blocks.append(block)

    # already in the session's identity map on the request path, so this is a
    # lookup rather than a query there
    owner = db.get(User, resume.user_id)

    return ResumeDocument(
        id=resume.id,
        title=resume.title,
        template=resume.template,
        full_name=resume.full_name or (owner.name if owner else None) or "",
        personal_info=personal_info,
        sections=blocks,
    )

from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select

from deps.auth import CurrentUser
from deps.db import Db
from enums import ResumeSectionType
from models.resume import Resume
from models.resume_section import ResumeSection


def _owned_resume(resume_id: UUID, db: Db, current_user: CurrentUser) -> Resume:
    stmt = select(Resume).where(
        Resume.id == resume_id, Resume.user_id == current_user.id
    )
    resume = db.scalars(stmt).one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return resume


CurrentUserResume = Annotated[Resume, Depends(_owned_resume)]


def _resume_section_ids(
    current_user_resume: CurrentUserResume, db: Db
) -> dict[ResumeSectionType, list[UUID]]:
    """The resume's membership list, grouped by type and in position order.

    ``position`` orders entries against others of the same type only, so the
    grouping is what the ordering is actually about. Resolving it here keeps
    the read endpoints from each re-deriving it, and hangs it off
    ``CurrentUserResume`` so the ownership check has already run.
    """
    stmt = (
        select(ResumeSection)
        .where(ResumeSection.resume_id == current_user_resume.id)
        .order_by(ResumeSection.position, ResumeSection.created_at)
    )

    ids_by_type: dict[ResumeSectionType, list[UUID]] = defaultdict(list)
    for row in db.scalars(stmt):
        ids_by_type[row.section_type].append(row.section_id)

    return ids_by_type


ResumeSectionIds = Annotated[
    dict[ResumeSectionType, list[UUID]], Depends(_resume_section_ids)
]

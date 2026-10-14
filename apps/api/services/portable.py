"""Importing sections from, and exporting them to, the portable JSON format.

An import adds everything in one transaction, so a file either arrives whole
or not at all. Each section goes through the snapshot appliers and gets the
same history entry an endpoint would have written, so the history shows
ordinary creates and nothing special about where they came from. Resumes are left alone: people build those in the app.
"""

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.skill import Skill
from schemas.personal_info import PersonalInfoRead
from schemas.portable import (
    ImportSummary,
    PortableEducation,
    PortableExperience,
    PortableLibrary,
    PortableLink,
    PortablePersonalInfo,
    PortableProject,
    PortableSkill,
)
from services.bullet_points import bullet_points_by_id, hydrate
from services.record_section import MAX_ATTEMPTS, stage_version
from services.sync_apply import apply_snapshot


def import_library(
    db: Session, user_id: UUID, library: PortableLibrary, *, dry_run: bool = False
) -> ImportSummary:
    """Add every section in the file for this user, or none of them.

    A dry run does all the same work and then rolls it back, so it catches
    anything the database would refuse as well as what validation already did.
    """
    for attempt in range(MAX_ATTEMPTS):
        try:
            summary = _write_library(db, user_id, library, dry_run=dry_run)
            if dry_run:
                db.rollback()
            else:
                db.commit()
        except IntegrityError:
            # somebody else took a history sequence number first; the whole
            # import is redone, since the entries and records land together
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                raise
            continue

        return summary

    # unreachable: the loop either returns or raises on its last attempt
    raise AssertionError("import_library fell out of its retry loop")


def _create(
    db: Session,
    user_id: UUID,
    record_type: SectionType,
    values: dict[str, Any],
) -> None:
    """Write one new section and its history entry.

    The entry is the section's read shape, which for every section kind is
    its fields plus its id — what the endpoints record after a create.
    """
    record_id = uuid4()
    apply_snapshot(db, user_id, record_type, record_id, values)
    stage_version(
        db,
        user_id,
        record_type,
        record_id,
        OperationType.CREATE,
        {"id": str(record_id), **values},
    )
    # The app's sessions don't autoflush (see ``deps.db``), and the next
    # history entry counts the ones already staged to take its sequence number.
    db.flush()


def _bullets(texts: list[str]) -> list[dict[str, Any]]:
    # the format carries no bold, so every bullet arrives plain
    return [{"text": text, "bolded": []} for text in texts]


def _write_library(
    db: Session, user_id: UUID, library: PortableLibrary, *, dry_run: bool
) -> ImportSummary:
    for info in library.personal_info:
        _create(db, user_id, SectionType.PERSONAL_INFO, info.model_dump(mode="json"))

    for education in library.education:
        _create(db, user_id, SectionType.EDUCATION, education.model_dump())

    for experience in library.experience:
        values = {
            **experience.model_dump(exclude={"bullet_points"}),
            "bullet_points": _bullets(experience.bullet_points),
        }
        _create(db, user_id, SectionType.EXPERIENCE, values)

    for project in library.projects:
        values = {
            **project.model_dump(exclude={"bullet_points"}),
            "bullet_points": _bullets(project.bullet_points),
        }
        _create(db, user_id, SectionType.PROJECT, values)

    # imported lists go after the ones the person already has, the same as
    # adding them one at a time would
    highest = db.scalar(
        select(func.max(Skill.position)).where(Skill.user_id == user_id)
    )
    next_position = 0 if highest is None else highest + 1
    for offset, skill in enumerate(library.skills):
        values = {**skill.model_dump(), "position": next_position + offset}
        _create(db, user_id, SectionType.SKILL, values)

    return ImportSummary(
        dry_run=dry_run,
        personal_info=len(library.personal_info),
        education=len(library.education),
        experience=len(library.experience),
        projects=len(library.projects),
        skills=len(library.skills),
    )


def export_library(db: Session, user_id: UUID) -> PortableLibrary:
    """Every section this user has, in the format import reads."""

    def owned(model: Any, *order: Any) -> list[Any]:
        return list(
            db.scalars(
                select(model)
                .where(model.user_id == user_id)
                .order_by(*order, model.created_at)
            )
        )

    experiences = owned(Expirence)
    projects = owned(Project)
    by_id = bullet_points_by_id(
        db,
        [
            bullet_id
            for row in [*experiences, *projects]
            for bullet_id in row.bullet_points
        ],
    )

    def texts(bullet_ids: list[UUID]) -> list[str]:
        return [bullet.text for bullet in hydrate(bullet_ids, by_id)]

    def link(value: Any) -> PortableLink | None:
        return None if value is None else PortableLink(url=value.url, label=value.label)

    personal_info = [
        PersonalInfoRead.model_validate(row) for row in owned(PersonalInfo)
    ]

    return PortableLibrary(
        personal_info=[
            PortablePersonalInfo(
                email=info.email,
                phone_number=info.phone_number,
                address=info.address,
                github=link(info.github),
                linkedin=link(info.linkedin),
                portfolio=link(info.portfolio),
            )
            for info in personal_info
        ],
        education=[
            PortableEducation(
                name=row.name,
                subheading=row.subheading,
                duration=row.duration,
                location=row.location,
            )
            for row in owned(Education)
        ],
        experience=[
            PortableExperience(
                company=row.company,
                position=row.position,
                duration=row.duration,
                location=row.location,
                bullet_points=texts(row.bullet_points),
            )
            for row in experiences
        ],
        projects=[
            PortableProject(
                name=row.name,
                link=row.link,
                github=row.github,
                technologies=list(row.technologies),
                bullet_points=texts(row.bullet_points),
            )
            for row in projects
        ],
        skills=[
            PortableSkill(name=row.name, items=list(row.items))
            for row in owned(Skill, Skill.position)
        ],
    )

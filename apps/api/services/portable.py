"""Importing a library from, and exporting it to, the portable JSON format.

An import creates everything in one transaction, so a file either arrives
whole or not at all. Each record goes through the same appliers a sync uses
and gets the same history entry an endpoint would have written, which means a
desktop syncing afterwards sees ordinary creates and nothing special about
where they came from.
"""

from collections import defaultdict
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enums import OperationType, ResumeSectionType, SectionType
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.skill import Skill
from schemas.education import EducationRead
from schemas.personal_info import PersonalInfoRead
from schemas.portable import (
    LIST_NAMES,
    ImportedResume,
    ImportSummary,
    PortableEducation,
    PortableExperience,
    PortableLibrary,
    PortableLink,
    PortablePersonalInfo,
    PortableProject,
    PortableResume,
    PortableSkill,
)
from schemas.skill import SkillRead
from services.bullet_points import bullet_points_by_id, hydrate
from services.record_section import MAX_ATTEMPTS, stage_version
from services.resume_snapshot import resume_snapshot, section_refs
from services.sync_apply import apply_snapshot


def import_library(
    db: Session, user_id: UUID, library: PortableLibrary, *, dry_run: bool = False
) -> ImportSummary:
    """Create everything in the file for this user, or nothing.

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
) -> UUID:
    """Write one new section and its history entry, returning its new id.

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
    _flush(db)
    return record_id


def _flush(db: Session) -> None:
    """Make what was just written visible to this transaction's own queries.

    The app's sessions don't autoflush (see ``deps.db``), and everything after
    this reads what came before: the next history entry counts the ones
    already staged to take its sequence number, and a resume's contact block
    is checked against the rows written for it here.
    """
    db.flush()


def _bullets(texts: list[str]) -> list[dict[str, Any]]:
    # the format carries no bold, so every bullet arrives plain
    return [{"text": text, "bolded": []} for text in texts]


def _write_library(
    db: Session, user_id: UUID, library: PortableLibrary, *, dry_run: bool
) -> ImportSummary:
    # file key -> new id, per list, for resolving the resumes' references
    ids: dict[str, dict[str, UUID]] = defaultdict(dict)

    def remember(list_name: str, key: str | None, record_id: UUID) -> None:
        if key is not None:
            ids[list_name][key] = record_id

    for info in library.personal_info:
        values = info.model_dump(mode="json", exclude={"key"})
        remember(
            "personal_info",
            info.key,
            _create(db, user_id, SectionType.PERSONAL_INFO, values),
        )

    for education in library.education:
        values = education.model_dump(exclude={"key"})
        remember(
            "education",
            education.key,
            _create(db, user_id, SectionType.EDUCATION, values),
        )

    for experience in library.experience:
        values = {
            **experience.model_dump(exclude={"key", "bullet_points"}),
            "bullet_points": _bullets(experience.bullet_points),
        }
        remember(
            "experience",
            experience.key,
            _create(db, user_id, SectionType.EXPERIENCE, values),
        )

    for project in library.projects:
        values = {
            **project.model_dump(exclude={"key", "bullet_points"}),
            "bullet_points": _bullets(project.bullet_points),
        }
        remember(
            "projects", project.key, _create(db, user_id, SectionType.PROJECT, values)
        )

    # imported lists go after the ones the person already has, the same as
    # adding them one at a time would
    highest = db.scalar(
        select(func.max(Skill.position)).where(Skill.user_id == user_id)
    )
    next_position = 0 if highest is None else highest + 1
    for offset, skill in enumerate(library.skills):
        values = {
            **skill.model_dump(exclude={"key"}),
            "position": next_position + offset,
        }
        remember("skills", skill.key, _create(db, user_id, SectionType.SKILL, values))

    resumes: list[ImportedResume] = []
    for resume in library.resumes:
        resume_id = _create_resume(db, user_id, resume, ids)
        resumes.append(ImportedResume(id=resume_id, title=resume.title))

    return ImportSummary(
        dry_run=dry_run,
        personal_info=len(library.personal_info),
        education=len(library.education),
        experience=len(library.experience),
        projects=len(library.projects),
        skills=len(library.skills),
        resumes=resumes,
    )


def _create_resume(
    db: Session,
    user_id: UUID,
    resume: PortableResume,
    ids: dict[str, dict[str, UUID]],
) -> UUID:
    personal_info_id = (
        None
        if resume.personal_info is None
        else ids["personal_info"][resume.personal_info]
    )
    refs = [
        {
            "section_type": section_type.value,
            "section_id": str(ids[LIST_NAMES[section_type]][key]),
            "position": position,
        }
        for section_type, keys in resume.sections.items()
        for position, key in enumerate(keys)
    ]

    # a type with sections but no place in the order would render nowhere,
    # so it goes at the end, as the resume endpoint does it
    section_order = list(resume.section_order)
    section_order += [
        section_type
        for section_type in resume.sections
        if resume.sections[section_type] and section_type not in section_order
    ]

    values = {
        "title": resume.title,
        "template": resume.template,
        "full_name": resume.full_name,
        "personal_info_id": None if personal_info_id is None else str(personal_info_id),
        "section_order": [section_type.value for section_type in section_order],
        "sections": refs,
    }

    record_id = uuid4()
    apply_snapshot(db, user_id, SectionType.RESUME, record_id, values)
    _flush(db)

    # recorded from the row, like the endpoint, so the entry carries the same
    # fields (updated_at included) any other resume version does
    row = db.get(Resume, record_id)
    assert row is not None
    stage_version(
        db,
        user_id,
        SectionType.RESUME,
        record_id,
        OperationType.CREATE,
        resume_snapshot(row, section_refs(db, record_id)),
    )
    _flush(db)
    return record_id


def export_library(db: Session, user_id: UUID) -> PortableLibrary:
    """Everything this user has, in the portable format.

    Each record's id is its key, so the resumes' references survive the trip
    and the file can be imported again as is.
    """

    def owned(model: Any, *order: Any) -> list[Any]:
        return list(
            db.scalars(
                select(model)
                .where(model.user_id == user_id)
                .order_by(*order, model.created_at)
            )
        )

    personal_info = [
        PersonalInfoRead.model_validate(row) for row in owned(PersonalInfo)
    ]
    education = [EducationRead.model_validate(row) for row in owned(Education)]
    experiences = owned(Expirence)
    projects = owned(Project)
    skills = [SkillRead.model_validate(row) for row in owned(Skill, Skill.position)]

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

    resumes: list[PortableResume] = []
    for row in owned(Resume):
        sections: dict[ResumeSectionType, list[str]] = defaultdict(list)
        for ref in section_refs(db, row.id):
            sections[ResumeSectionType(ref["section_type"])].append(ref["section_id"])

        resumes.append(
            PortableResume(
                title=row.title,
                template=row.template,
                full_name=row.full_name,
                personal_info=(
                    None if row.personal_info_id is None else str(row.personal_info_id)
                ),
                section_order=[
                    ResumeSectionType(section_type)
                    for section_type in row.section_order
                ],
                sections=dict(sections),
            )
        )

    return PortableLibrary(
        personal_info=[
            PortablePersonalInfo(
                key=str(info.id),
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
            PortableEducation(key=str(item.id), **item.model_dump(exclude={"id"}))
            for item in education
        ],
        experience=[
            PortableExperience(
                key=str(row.id),
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
                key=str(row.id),
                name=row.name,
                link=row.link,
                github=row.github,
                technologies=list(row.technologies),
                bullet_points=texts(row.bullet_points),
            )
            for row in projects
        ],
        skills=[
            PortableSkill(key=str(skill.id), name=skill.name, items=skill.items)
            for skill in skills
        ],
        resumes=resumes,
    )

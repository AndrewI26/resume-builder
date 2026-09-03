"""Writing a change from somewhere else into this database.

The history stores what a record looked like, as the same JSON the API returns
for it. Applying one means turning that back into rows — the reverse of how it
was written — for whichever kind of record it describes.

Two things make this less mechanical than it sounds.

A record keeps its id. That is what makes a desktop library and an account the
same library rather than two with matching contents: the same experience is the
same UUID on both sides, and only its owner differs. So these write the id they
are given instead of generating one, and an apply is an upsert — the record may
or may not already be here.

And experiences and projects keep their bullet points in a separate table,
referenced by an ordered array of ids. Those ids are local bookkeeping rather
than part of the record, so applying replaces the rows outright rather than
trying to match them up; the snapshot carries the text, which is the part
anybody meant.
"""

from typing import Any, Protocol
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from enums import ResumeSectionType, SectionType
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.resume_section import ResumeSection
from models.skill import Skill
from schemas.education import EducationCreate
from schemas.expirence import ExpirenceCreate
from schemas.personal_info import PersonalInfoCreate
from schemas.project import ProjectCreate
from schemas.resume import ResumeEdit
from schemas.skill import SkillEdit
from services.bullet_points import delete_bullet_points, insert_bullet_points


class UnapplicableChange(Exception):
    """The snapshot does not describe something that can be written here.

    Either it is malformed, or it points at a record belonging to someone else
    — a resume naming a stranger's contact block, say. Both are the caller's
    problem rather than a server fault.
    """


class Applier(Protocol):
    def __call__(
        self, db: Session, user_id: UUID, record_id: UUID, snapshot: dict[str, Any]
    ) -> None: ...


def _replace_bullet_points(
    db: Session, existing: list[UUID], bullets: Any
) -> list[UUID]:
    """Swap a record's bullet point rows for the ones in the snapshot."""
    delete_bullet_points(db, existing)
    return insert_bullet_points(db, bullets)


def _apply_education(
    db: Session, user_id: UUID, record_id: UUID, snapshot: dict[str, Any]
) -> None:
    fields = EducationCreate.model_validate(snapshot)
    row = db.get(Education, record_id)

    if row is None:
        db.add(Education(id=record_id, user_id=user_id, **fields.model_dump()))
        return

    for name, value in fields.model_dump().items():
        setattr(row, name, value)


def _apply_skill(
    db: Session, user_id: UUID, record_id: UUID, snapshot: dict[str, Any]
) -> None:
    fields = SkillEdit.model_validate(snapshot)
    row = db.get(Skill, record_id)

    if row is None:
        db.add(Skill(id=record_id, user_id=user_id, **fields.model_dump()))
        return

    for name, value in fields.model_dump().items():
        setattr(row, name, value)


def _apply_personal_info(
    db: Session, user_id: UUID, record_id: UUID, snapshot: dict[str, Any]
) -> None:
    fields = PersonalInfoCreate.model_validate(snapshot)
    values = fields.model_dump(mode="json")
    row = db.get(PersonalInfo, record_id)

    if row is None:
        db.add(PersonalInfo(id=record_id, user_id=user_id, **values))
        return

    for name, value in values.items():
        setattr(row, name, value)


def _apply_expirence(
    db: Session, user_id: UUID, record_id: UUID, snapshot: dict[str, Any]
) -> None:
    fields = ExpirenceCreate.model_validate(snapshot)
    row = db.get(Expirence, record_id)
    existing = list(row.bullet_points) if row is not None else []
    bullet_ids = _replace_bullet_points(db, existing, fields.bullet_points)

    values = fields.model_dump(exclude={"bullet_points"})

    if row is None:
        db.add(
            Expirence(id=record_id, user_id=user_id, bullet_points=bullet_ids, **values)
        )
        return

    for name, value in values.items():
        setattr(row, name, value)
    row.bullet_points = bullet_ids


def _apply_project(
    db: Session, user_id: UUID, record_id: UUID, snapshot: dict[str, Any]
) -> None:
    fields = ProjectCreate.model_validate(snapshot)
    row = db.get(Project, record_id)
    existing = list(row.bullet_points) if row is not None else []
    bullet_ids = _replace_bullet_points(db, existing, fields.bullet_points)

    values = fields.model_dump(exclude={"bullet_points"})

    if row is None:
        db.add(
            Project(id=record_id, user_id=user_id, bullet_points=bullet_ids, **values)
        )
        return

    for name, value in values.items():
        setattr(row, name, value)
    row.bullet_points = bullet_ids


def _apply_resume(
    db: Session, user_id: UUID, record_id: UUID, snapshot: dict[str, Any]
) -> None:
    fields = ResumeEdit.model_validate(snapshot)

    # a resume points at a contact block, and pointing at somebody else's would
    # let a push read across accounts on the next render
    if fields.personal_info_id is not None:
        owner = db.scalar(
            select(PersonalInfo.user_id).where(
                PersonalInfo.id == fields.personal_info_id
            )
        )
        if owner != user_id:
            raise UnapplicableChange(
                "the resume names a contact block that is not this account's"
            )

    values = fields.model_dump(exclude={"section_order"})
    section_order = [
        section_type.value for section_type in (fields.section_order or [])
    ]

    row = db.get(Resume, record_id)
    if row is None:
        row = Resume(
            id=record_id, user_id=user_id, section_order=section_order, **values
        )
        db.add(row)
    else:
        for name, value in values.items():
            setattr(row, name, value)
        row.section_order = section_order

    _apply_membership(db, user_id, record_id, snapshot.get("sections", []))


def _apply_membership(
    db: Session, user_id: UUID, resume_id: UUID, sections: Any
) -> None:
    """Replace which sections the resume has chosen.

    Replaced wholesale rather than merged, for the same reason the endpoint
    does it that way: the list states the intended order outright, so patching
    it would mean inferring an order that was already given.
    """
    db.execute(delete(ResumeSection).where(ResumeSection.resume_id == resume_id))

    for ref in sections or []:
        try:
            section_type = ResumeSectionType(ref["section_type"])
            section_id = UUID(str(ref["section_id"]))
            position = int(ref.get("position", 0))
        except (KeyError, TypeError, ValueError) as error:
            raise UnapplicableChange(
                f"unreadable section reference: {error}"
            ) from error

        db.add(
            ResumeSection(
                resume_id=resume_id,
                section_type=section_type,
                section_id=section_id,
                position=position,
            )
        )


APPLIERS: dict[SectionType, Applier] = {
    SectionType.EDUCATION: _apply_education,
    SectionType.EXPERIENCE: _apply_expirence,
    SectionType.PERSONAL_INFO: _apply_personal_info,
    SectionType.PROJECT: _apply_project,
    SectionType.SKILL: _apply_skill,
    SectionType.RESUME: _apply_resume,
}

MODELS: dict[SectionType, Any] = {
    SectionType.EDUCATION: Education,
    SectionType.EXPERIENCE: Expirence,
    SectionType.PERSONAL_INFO: PersonalInfo,
    SectionType.PROJECT: Project,
    SectionType.SKILL: Skill,
    SectionType.RESUME: Resume,
}


def owner_of(db: Session, record_type: SectionType, record_id: UUID) -> UUID | None:
    """Who this record belongs to here, or None if it is not here."""
    row = db.get(MODELS[record_type], record_id)
    return None if row is None else row.user_id


def apply_snapshot(
    db: Session,
    user_id: UUID,
    record_type: SectionType,
    record_id: UUID,
    snapshot: dict[str, Any],
) -> None:
    """Write a record into this database as the snapshot describes it."""
    # Ids are chosen by whichever side created the record, so a pushed id is a
    # claim rather than a fact. Without this, naming somebody else's id would
    # overwrite their row: the caller's own history says nothing about a record
    # that was never theirs, so the version check upstream would see a new
    # record and wave it through.
    existing_owner = owner_of(db, record_type, record_id)
    if existing_owner is not None and existing_owner != user_id:
        raise UnapplicableChange("that record belongs to someone else")

    try:
        APPLIERS[record_type](db, user_id, record_id, snapshot)
    except ValidationError as error:
        raise UnapplicableChange(
            f"the snapshot is not a {record_type.value}"
        ) from error


def apply_delete(
    db: Session, user_id: UUID, record_type: SectionType, record_id: UUID
) -> None:
    """Remove a record, if it is still here and belongs to this account.

    A delete that finds nothing is not a failure. Two sides can decide to
    delete the same thing, and the outcome both of them wanted has happened.
    """
    model = MODELS[record_type]
    row = db.get(model, record_id)

    if row is None or row.user_id != user_id:
        return

    if record_type in (SectionType.EXPERIENCE, SectionType.PROJECT):
        delete_bullet_points(db, list(row.bullet_points))

    db.delete(row)

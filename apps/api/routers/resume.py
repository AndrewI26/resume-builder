from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from deps.auth import CurrentUser
from deps.db import Db
from deps.resume import CurrentUserResume, ResumeSectionIds
from enums import ResumeSectionType
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.resume_section import ResumeSection
from models.skill import Skill
from schemas.education import EducationRead
from schemas.personal_info import PersonalInfoRead
from schemas.resume import (
    EducationBlock,
    ExperienceBlock,
    ProjectBlock,
    ResumeCompileRequest,
    ResumeCreate,
    ResumeDocument,
    ResumeEdit,
    ResumeRead,
    ResumeSectionRef,
    ResumeSectionsReplace,
    SectionBlock,
    SkillBlock,
)
from schemas.skill import SkillRead
from services.bullet_points import bullet_points_by_id
from services.compiler import (
    CompilerUnavailable,
    DocumentRejected,
    compile_to_pdf,
)
from services.sections import expirence_to_read, project_to_read

router = APIRouter(prefix="/resumes", tags=["Resume"])

# the table each section type's ids live in. ``resume_sections`` is polymorphic
# by hand, so every lookup starts here.
SECTION_MODELS: dict[ResumeSectionType, Any] = {
    ResumeSectionType.EDUCATION: Education,
    ResumeSectionType.EXPERIENCE: Expirence,
    ResumeSectionType.PROJECT: Project,
    ResumeSectionType.SKILL: Skill,
}


def _check_personal_info(
    db: Session, personal_info_id: UUID | None, user_id: UUID
) -> None:
    """Refuse to point a resume at contact details belonging to someone else."""
    if personal_info_id is None:
        return

    stmt = select(PersonalInfo.id).where(
        PersonalInfo.id == personal_info_id, PersonalInfo.user_id == user_id
    )
    if db.scalars(stmt).one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such personal info",
        )


def _check_sections_owned(
    db: Session, ids_by_type: dict[ResumeSectionType, list[UUID]], user_id: UUID
) -> None:
    """Every referenced section must exist and belong to the caller.

    Without this a caller could staple another user's experience onto their own
    resume and read it back through the document endpoint.
    """
    for section_type, ids in ids_by_type.items():
        model = SECTION_MODELS[section_type]
        stmt = select(model.id).where(model.id.in_(set(ids)), model.user_id == user_id)
        found = set(db.scalars(stmt))

        missing = [str(section_id) for section_id in ids if section_id not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No such {section_type.value}: {', '.join(missing)}",
            )


def _ordered(rows: Sequence[Any], ids: Sequence[UUID]) -> list[Any]:
    """Put fetched rows back into the order their ids were listed in."""
    by_id = {row.id: row for row in rows}
    return [by_id[section_id] for section_id in ids if section_id in by_id]


@router.get("/", response_model=list[ResumeRead])
def get_resumes(current_user: CurrentUser, db: Db) -> Sequence[Resume]:
    stmt = (
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at)
    )
    return db.scalars(stmt).all()


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(current_user_resume: CurrentUserResume) -> Resume:
    return current_user_resume


@router.post("/", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def create_resume(
    resume: ResumeCreate, current_user: CurrentUser, db: Db
) -> ResumeRead:
    _check_personal_info(db, resume.personal_info_id, current_user.id)

    # validate before inserting anything: a bad reference should leave no
    # trace, without depending on the session being discarded on the way out
    ids_by_type = _grouped(resume.sections)
    _check_sections_owned(db, ids_by_type, current_user.id)

    stmt = (
        insert(Resume)
        .values(
            user_id=current_user.id,
            title=resume.title,
            template=resume.template,
            full_name=resume.full_name,
            personal_info_id=resume.personal_info_id,
            section_order=[section_type.value for section_type in resume.section_order],
        )
        .returning(Resume)
    )
    new_resume = db.scalars(stmt).one()

    if ids_by_type:
        _write_sections(db, new_resume, ids_by_type)

    result = ResumeRead.model_validate(new_resume)
    db.commit()

    return result


@router.put("/{resume_id}", response_model=ResumeRead)
def edit_resume(
    resume_id: UUID, resume: ResumeEdit, current_user: CurrentUser, db: Db
) -> ResumeRead:
    _check_personal_info(db, resume.personal_info_id, current_user.id)

    stmt = (
        update(Resume)
        .where(Resume.id == resume_id, Resume.user_id == current_user.id)
        .values(
            title=resume.title,
            template=resume.template,
            full_name=resume.full_name,
            personal_info_id=resume.personal_info_id,
            section_order=[section_type.value for section_type in resume.section_order],
        )
        .returning(Resume)
    )
    edited_resume = db.scalars(stmt).one_or_none()
    if edited_resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = ResumeRead.model_validate(edited_resume)
    db.commit()

    return result


@router.delete("/{resume_id}", response_model=ResumeRead)
def delete_resume(resume_id: UUID, current_user: CurrentUser, db: Db) -> ResumeRead:
    stmt = (
        delete(Resume)
        .where(Resume.id == resume_id, Resume.user_id == current_user.id)
        .returning(Resume)
    )
    deleted_resume = db.scalars(stmt).one_or_none()
    if deleted_resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = ResumeRead.model_validate(deleted_resume)
    db.commit()

    return result


@router.get("/{resume_id}/sections", response_model=ResumeSectionsReplace)
def get_resume_sections(section_ids: ResumeSectionIds) -> ResumeSectionsReplace:
    return ResumeSectionsReplace(
        sections=[
            ResumeSectionRef(section_type=section_type, section_id=section_id)
            for section_type in sorted(section_ids, key=lambda t: t.value)
            for section_id in section_ids[section_type]
        ]
    )


def _grouped(refs: Sequence[ResumeSectionRef]) -> dict[ResumeSectionType, list[UUID]]:
    """Collect references by type, keeping the order they were listed in."""
    ids_by_type: dict[ResumeSectionType, list[UUID]] = defaultdict(list)
    for ref in refs:
        ids_by_type[ref.section_type].append(ref.section_id)

    return ids_by_type


def _write_sections(
    db: Session,
    resume: Resume,
    ids_by_type: dict[ResumeSectionType, list[UUID]],
) -> None:
    """Replace a resume's membership list.

    Position is the index within each type's run, so the request body states
    the intended order outright rather than patching it. Ownership is the
    caller's job to check first — see `_check_sections_owned`.
    """
    db.execute(delete(ResumeSection).where(ResumeSection.resume_id == resume.id))

    rows = [
        {
            "resume_id": resume.id,
            "section_type": section_type,
            "section_id": section_id,
            "position": position,
        }
        for section_type, ids in ids_by_type.items()
        for position, section_id in enumerate(ids)
    ]
    if rows:
        db.execute(insert(ResumeSection), rows)

    # a type that was attached but never ordered would render nowhere, so give
    # it a place at the end rather than silently dropping it
    missing = [
        section_type.value
        for section_type in ids_by_type
        if section_type.value not in resume.section_order
    ]
    if missing:
        resume.section_order = list(resume.section_order) + missing


@router.put("/{resume_id}/sections", response_model=ResumeSectionsReplace)
def replace_resume_sections(
    payload: ResumeSectionsReplace,
    current_user: CurrentUser,
    db: Db,
    current_user_resume: CurrentUserResume,
) -> ResumeSectionsReplace:
    """Replace the whole membership list.

    Position is taken from the index within each type's run, so the request
    body states the intended order outright rather than patching it.
    """

    ids_by_type = _grouped(payload.sections)
    _check_sections_owned(db, ids_by_type, current_user.id)
    _write_sections(db, current_user_resume, ids_by_type)

    db.commit()

    return payload


@router.get("/{resume_id}/document", response_model=ResumeDocument)
def get_resume_document(
    current_user: CurrentUser,
    db: Db,
    current_user_resume: CurrentUserResume,
    ids_by_type: ResumeSectionIds,
) -> ResumeDocument:
    """The whole resume, resolved and ordered, in the shape a renderer wants.

    Bullet points are hydrated, blocks arrive in ``section_order`` and empty
    ones are dropped, so a client can walk this straight into a template.
    """

    personal_info: PersonalInfoRead | None = None
    if current_user_resume.personal_info_id is not None:
        personal_info_stmt = select(PersonalInfo).where(
            PersonalInfo.id == current_user_resume.personal_info_id,
            PersonalInfo.user_id == current_user.id,
        )
        row = db.scalars(personal_info_stmt).one_or_none()
        if row is not None:
            personal_info = PersonalInfoRead.model_validate(row)

    blocks: list[SectionBlock] = []
    for value in current_user_resume.section_order:
        ids = ids_by_type.get(ResumeSectionType(value), [])
        if not ids:
            continue

        block = _build_block(db, current_user.id, ResumeSectionType(value), ids)
        # a section whose rows were all deleted leaves stale ids behind; an
        # empty block would render as a bare heading, so drop it
        if block.items:
            blocks.append(block)

    return ResumeDocument(
        id=current_user_resume.id,
        title=current_user_resume.title,
        template=current_user_resume.template,
        full_name=current_user_resume.full_name or current_user.name or "",
        personal_info=personal_info,
        sections=blocks,
    )


def _build_block(
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


def _pdf_filename(title: str) -> str:
    """A safe download name derived from the resume's title."""
    slug = "".join(
        character if character.isalnum() else "-" for character in title
    ).strip("-")
    return f"{slug.lower() or 'resume'}.pdf"


@router.post(
    "/{resume_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def compile_resume_pdf(
    payload: ResumeCompileRequest,
    current_user_resume: CurrentUserResume,
) -> Response:
    """Typeset LaTeX into a PDF.

    The resume is what authorizes the call and what names the file; the source
    itself comes from the caller, generated in their browser from the document
    endpoint. Nothing here can confirm it is the same document, so the compile
    service treats every request as hostile and is sandboxed for it.
    """

    try:
        pdf = compile_to_pdf(payload.source)
    except DocumentRejected as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            # the tail is where the engine says what it actually objected to
            detail=error.log[-2000:] or "the document failed to compile",
        ) from error
    except CompilerUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF export is unavailable",
        ) from error

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_pdf_filename(current_user_resume.title)}"'
            )
        },
    )

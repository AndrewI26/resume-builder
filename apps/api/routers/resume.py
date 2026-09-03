import asyncio
from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from config import get_settings
from deps.auth import CurrentUser
from deps.db import Db
from deps.notify import Notifier
from deps.resume import CurrentUserResume, ResumeSectionIds
from enums import OperationType, ResumeSectionType, SectionType
from models.personal_info import PersonalInfo
from models.resume import Resume
from models.resume_section import ResumeSection
from schemas.resume import (
    ResumeCreate,
    ResumeDocument,
    ResumeEdit,
    ResumeRead,
    ResumeSectionRef,
    ResumeSectionsReplace,
)
from services import pdf_queue
from services.compiler import CompilerUnavailable, DocumentRejected
from services.local_compile import compile_resume_pdf_locally
from services.pdf_queue import ResumeMissing
from services.record_section import record_version
from services.resume_document import SECTION_MODELS, build_resume_document
from services.resume_snapshot import resume_snapshot, section_refs

settings = get_settings()

router = APIRouter(prefix="/resumes", tags=["Resume"])


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
    db.flush()
    snapshot = resume_snapshot(new_resume, section_refs(db, new_resume.id))
    db.commit()

    record_version(
        db,
        current_user.id,
        SectionType.RESUME,
        new_resume.id,
        OperationType.CREATE,
        snapshot,
    )

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
    snapshot = resume_snapshot(edited_resume, section_refs(db, edited_resume.id))
    db.commit()

    record_version(
        db,
        current_user.id,
        SectionType.RESUME,
        edited_resume.id,
        OperationType.UPDATE,
        snapshot,
    )

    return result


@router.delete("/{resume_id}", response_model=ResumeRead)
def delete_resume(resume_id: UUID, current_user: CurrentUser, db: Db) -> ResumeRead:
    stmt = (
        delete(Resume)
        .where(Resume.id == resume_id, Resume.user_id == current_user.id)
        .returning(Resume)
    )
    # read the membership first: deleting the resume cascades these away, and
    # the history is the only place a deleted resume still exists
    sections = section_refs(db, resume_id)

    deleted_resume = db.scalars(stmt).one_or_none()
    if deleted_resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = ResumeRead.model_validate(deleted_resume)
    snapshot = resume_snapshot(deleted_resume, sections)
    db.commit()

    record_version(
        db,
        current_user.id,
        SectionType.RESUME,
        resume_id,
        OperationType.DELETE,
        snapshot,
    )

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

    db.flush()
    snapshot = resume_snapshot(
        current_user_resume, section_refs(db, current_user_resume.id)
    )
    db.commit()

    # the membership is part of the resume rather than a record of its own, so
    # changing it is a new version of the resume
    record_version(
        db,
        current_user.id,
        SectionType.RESUME,
        current_user_resume.id,
        OperationType.UPDATE,
        snapshot,
    )

    return payload


@router.get("/{resume_id}/document", response_model=ResumeDocument)
def get_resume_document(
    db: Db,
    current_user_resume: CurrentUserResume,
    ids_by_type: ResumeSectionIds,
) -> ResumeDocument:
    """The whole resume, resolved and ordered, in the shape a renderer wants.

    The PDF worker builds the same structure from the same rows, so this stays
    a view onto shared logic rather than a second implementation of it.
    """
    return build_resume_document(db, current_user_resume, ids_by_type)


# how long the request waits on the worker. Comfortably past the engine's own
# ceiling, so a slow compile still lands rather than racing this.
_RESULT_TIMEOUT = 45.0


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
async def compile_resume_pdf(
    current_user_resume: CurrentUserResume,
    db: Db,
    notifier: Notifier,
) -> Response:
    """Typeset the resume and hand back the PDF.

    The source is generated in a worker from this resume's own rows, so nothing
    about the document crosses the wire on the way in and there is no
    caller-supplied LaTeX to distrust.

    The wait here is deliberate: the client asked for a file and gets one in
    the same response. The queue is not hiding the work, it is bounding how
    much of it runs at once — a compile is CPU-bound, and unbounded exports
    would take the host down rather than merely queue. A local install has no
    host to protect and no queue to reach, so it typesets in this process
    instead; both paths raise the same failures, which is why only the call
    differs and none of the handling below does.
    """
    try:
        if settings.is_local:
            # No queue, and nothing to protect a host from: one person, one
            # compile, on the request they are waiting for.
            pdf = await compile_resume_pdf_locally(db, current_user_resume)
        else:
            if notifier is None:
                # the lifespan did not start one, so nothing would ever hear
                # that the job finished
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="PDF export is unavailable",
                )

            # a job per request rather than one per resume: a finished job is
            # kept for a short while, and re-using an id would serve a stale
            # PDF to someone who edited and exported again
            job_id = uuid4()

            # registered before the job exists, so a compile that finishes
            # immediately still finds someone listening
            finished = notifier.expect(job_id)

            try:
                # the session is the synchronous one, and this is an async
                # endpoint; a blocking write here would stall the workers
                # sharing this loop
                await asyncio.to_thread(
                    pdf_queue.enqueue, db, current_user_resume.id, job_id
                )
            except Exception:
                notifier.forget(job_id)
                raise

            await notifier.wait(job_id, finished, _RESULT_TIMEOUT)
            pdf = await asyncio.to_thread(pdf_queue.result, db, job_id)
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PDF export took too long",
        ) from None
    except ResumeMissing:
        # deleted between being asked for and being built
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None
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

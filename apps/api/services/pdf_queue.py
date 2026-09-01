"""The PDF job queue, kept in Postgres.

The table is the queue. Inserting a row and notifying is what a producer does;
claiming a row with ``FOR UPDATE SKIP LOCKED`` is what makes N workers safe
without anything coordinating them. Postgres is already here and already
transactional, so a job cannot be handed out twice and cannot go missing
between the insert and the wake-up: both happen in one transaction, and
``NOTIFY`` is delivered by the commit.

A row carries its own result. The request that inserted it is still open
waiting for it, so the PDF comes back inline rather than through storage both
ends would have to reach, and the row is deleted shortly after.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from enums import PdfJobErrorKind, PdfJobStatus
from models.pdf_job import PdfJob
from services.compiler import CompilerUnavailable, DocumentRejected

# Workers listen here for "a job was queued", and the API listens on the second
# for "job <id> reached a terminal state".
CHANNEL_QUEUED = "pdf_jobs"
CHANNEL_DONE = "pdf_jobs_done"

# One resume is one job, so a retry would re-run a compile that failed for a
# reason retrying cannot change: the document is the same every time.
MAX_TRIES = 1

# How long a finished row sticks around for its waiting request to read.
# Matches what arq's ``keep_result`` gave us.
RESULT_TTL = timedelta(seconds=60)

# A claimed job whose worker never came back — the process was killed, or the
# whole API restarted mid-compile. Comfortably longer than the compile's own
# ceiling so a slow-but-alive job is never stolen from under itself.
LEASE = timedelta(seconds=90)


class ResumeMissing(Exception):
    """The resume was deleted between enqueueing the job and running it."""


@dataclass(frozen=True)
class ClaimedJob:
    """What a worker needs off a claimed row.

    Plain values rather than the mapped instance: the worker claims on one
    session, compiles, then finishes on another, and an ORM object outlives
    neither boundary usefully.
    """

    id: uuid.UUID
    resume_id: uuid.UUID


def _notify(db: Session, channel: str, payload: str = "") -> None:
    """Queue a notification to fire when this transaction commits.

    ``pg_notify`` rather than ``NOTIFY`` so the payload is a bound parameter
    instead of something spliced into SQL.
    """
    db.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": channel, "payload": payload},
    )


def enqueue(db: Session, resume_id: uuid.UUID) -> uuid.UUID:
    """Queue a compile for ``resume_id`` and wake a worker. Returns the job id.

    The insert and the wake-up share a transaction, so there is no moment where
    the row is visible but no notification is coming, nor the reverse.
    """
    job = PdfJob(resume_id=resume_id, status=PdfJobStatus.QUEUED)
    db.add(job)
    db.flush()

    _notify(db, CHANNEL_QUEUED)
    db.commit()

    return job.id


def claim(db: Session) -> ClaimedJob | None:
    """Take the oldest queued job, or return None if there is nothing to do.

    ``SKIP LOCKED`` is the whole trick: a worker steps over rows another worker
    has locked rather than queueing behind them, so the pool scales by adding
    processes and nothing has to hand out work.
    """
    stmt = (
        select(PdfJob)
        .where(PdfJob.status == PdfJobStatus.QUEUED)
        .order_by(PdfJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        # end the snapshot this read opened; an idle worker holding one open
        # would pin the tuples the reaper wants to remove
        db.rollback()
        return None

    job.status = PdfJobStatus.RUNNING
    job.attempts += 1
    job.started_at = datetime.now(UTC)

    claimed = ClaimedJob(id=job.id, resume_id=job.resume_id)
    db.commit()

    return claimed


def succeed(db: Session, job_id: uuid.UUID, pdf: bytes) -> None:
    """Record the finished PDF and wake whoever is waiting on it."""
    _complete(db, job_id, status=PdfJobStatus.SUCCEEDED, pdf=pdf)


def fail(
    db: Session, job_id: uuid.UUID, kind: PdfJobErrorKind, detail: str = ""
) -> None:
    """Record why the compile failed, in the terms the endpoint answers in."""
    _complete(
        db,
        job_id,
        status=PdfJobStatus.FAILED,
        error_kind=kind,
        error_detail=detail or None,
    )


def _complete(
    db: Session,
    job_id: uuid.UUID,
    *,
    status: PdfJobStatus,
    pdf: bytes | None = None,
    error_kind: PdfJobErrorKind | None = None,
    error_detail: str | None = None,
) -> None:
    job = db.get(PdfJob, job_id)
    if job is None:
        # the resume was deleted under us and took the row with it; there is
        # nobody left to tell
        return

    job.status = status
    job.pdf = pdf
    job.error_kind = error_kind
    job.error_detail = error_detail
    job.finished_at = datetime.now(UTC)

    _notify(db, CHANNEL_DONE, str(job_id))
    db.commit()


def result(db: Session, job_id: uuid.UUID) -> bytes:
    """The PDF for a finished job, or the failure it recorded, raised.

    The worker cannot throw across a table, so it wrote down which exception it
    would have raised and this puts it back — which is what lets the endpoint
    keep one set of ``except`` arms whatever ran the job.
    """
    job = db.get(PdfJob, job_id)
    if job is None:
        # deleted by the resume's cascade while the request waited
        raise ResumeMissing(str(job_id))

    if job.status is PdfJobStatus.SUCCEEDED and job.pdf is not None:
        return job.pdf

    detail = job.error_detail or ""
    match job.error_kind:
        case PdfJobErrorKind.MISSING:
            raise ResumeMissing(detail)
        case PdfJobErrorKind.REJECTED:
            raise DocumentRejected(detail)
        case _:
            # unavailable, or a terminal row with nothing recorded on it
            raise CompilerUnavailable(detail or "the compile did not finish")


def reap(db: Session, now: datetime | None = None) -> int:
    """Clear out finished rows and rescue abandoned ones. Returns rows removed.

    Two jobs in one pass. Terminal rows past their TTL are deleted — their
    request has long since been answered, and the PDF bytes are the largest
    thing in the database if they are left to pile up. Rows still ``running``
    past the lease belonged to a worker that died; they are marked failed so a
    waiter gets an answer rather than its full timeout.
    """
    now = now or datetime.now(UTC)

    abandoned = db.execute(
        select(PdfJob.id).where(
            PdfJob.status == PdfJobStatus.RUNNING,
            PdfJob.started_at < now - LEASE,
        )
    ).scalars()

    for job_id in abandoned:
        # MAX_TRIES is 1, so there is no attempt left to give it
        fail(
            db,
            job_id,
            PdfJobErrorKind.UNAVAILABLE,
            "the worker did not finish the compile",
        )

    deleted = (
        db.query(PdfJob)
        .filter(
            PdfJob.status.in_((PdfJobStatus.SUCCEEDED, PdfJobStatus.FAILED)),
            PdfJob.finished_at < now - RESULT_TTL,
        )
        .delete(synchronize_session=False)
    )
    db.commit()

    return int(deleted)


def pending(db: Session) -> int:
    """How many jobs are queued or running — for tests and diagnostics."""
    return int(
        db.execute(
            select(func.count(PdfJob.id)).where(
                PdfJob.status.in_((PdfJobStatus.QUEUED, PdfJobStatus.RUNNING))
            )
        ).scalar_one()
    )

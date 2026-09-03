import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, enum_values
from enums import PdfJobErrorKind, PdfJobStatus


class PdfJob(Base):
    """One request to typeset one resume, and wherever that request got to.

    This table is the queue. A row is claimed by exactly one worker through
    ``FOR UPDATE SKIP LOCKED``, and it carries its own result: the PDF bytes on
    success, or which failure to raise on the way out. The endpoint that
    inserted the row is still holding the request open waiting for it, which is
    why the row is short-lived — the reaper deletes it once the response has
    had its chance to read it.
    """

    __tablename__ = "pdf_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # a deleted resume takes its pending jobs with it: the compile would only
    # find nothing to read
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[PdfJobStatus] = mapped_column(
        Enum(PdfJobStatus, name="pdf_job_status", values_callable=enum_values),
        nullable=False,
        default=PdfJobStatus.QUEUED,
    )

    # how many times a worker has claimed this row. Compared against
    # ``MAX_TRIES`` when recovering a job whose worker died mid-compile.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # the result, inline. A resume PDF is tens of kilobytes and lives for
    # seconds, so it travels back through the row rather than through a
    # filesystem the API and its workers would both have to reach.
    pdf: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    error_kind: Mapped[PdfJobErrorKind | None] = mapped_column(
        Enum(PdfJobErrorKind, name="pdf_job_error_kind", values_callable=enum_values),
        nullable=True,
    )
    # the engine's log tail for a rejection, or the reason it could not run
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # the claim query's whole predicate. Partial, because the rows worth
        # indexing are the handful still waiting — not the terminal ones the
        # reaper is about to delete.
        Index(
            "ix_pdf_jobs_queued",
            "status",
            "created_at",
            postgresql_where=status == PdfJobStatus.QUEUED,
        ),
    )

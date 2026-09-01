"""add pdf_jobs queue table

The PDF queue moves from Redis/arq into Postgres. This table is the queue
itself: the endpoint inserts a row and waits, a worker claims it with
``FOR UPDATE SKIP LOCKED``, and the result — the PDF bytes, or which failure
to raise — comes back on the same row.

Rows are short-lived by design. The reaper deletes terminal ones once the
waiting response has had its chance to read them, so the partial index below
covers the only rows ever scanned in bulk: the handful still queued.

Revision ID: 72e148f55704
Revises: 8b55e1df3c16
Create Date: 2026-09-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "72e148f55704"
down_revision: str | Sequence[str] | None = "8b55e1df3c16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pdf_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "succeeded", "failed", name="pdf_job_status"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("pdf", sa.LargeBinary(), nullable=True),
        sa.Column(
            "error_kind",
            sa.Enum(
                "missing", "rejected", "unavailable", name="pdf_job_error_kind"
            ),
            nullable=True,
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # a deleted resume takes its pending jobs with it: the compile would
        # only find nothing to read
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # exactly the claim query's predicate and ordering
    op.create_index(
        "ix_pdf_jobs_queued",
        "pdf_jobs",
        ["status", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        op.f("ix_pdf_jobs_resume_id"), "pdf_jobs", ["resume_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pdf_jobs_resume_id"), table_name="pdf_jobs")
    op.drop_index(
        "ix_pdf_jobs_queued",
        table_name="pdf_jobs",
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.drop_table("pdf_jobs")

    # dropping the table leaves the types behind, and a re-upgrade would then
    # fail creating them a second time
    sa.Enum(name="pdf_job_status").drop(op.get_bind())
    sa.Enum(name="pdf_job_error_kind").drop(op.get_bind())

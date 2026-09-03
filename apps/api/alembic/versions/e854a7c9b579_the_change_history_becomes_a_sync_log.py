"""the change history becomes a sync log

Two changes, both so that a desktop and an account can be reconciled.

``seq`` orders everything one user has changed, across every kind of record, so
a sync can ask for "everything since 812" and be given it in the order it
happened. Existing rows are numbered by when they were written, which is the
order they did happen in.

And the history gains a kind: a resume. It is not a section of anything, but it
is a thing a person edits, so it belongs in the same sequence as the rest
rather than in a second history that would have to be merged with this one.

Revision ID: e854a7c9b579
Revises: 8b55e1df3c16
Create Date: 2026-09-03 11:56:35.499687

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e854a7c9b579"
down_revision: str | Sequence[str] | None = "8b55e1df3c16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Numbers each user's existing history in the order it was written. A
# correlated count rather than a window function or an UPDATE ... FROM, both of
# which are spelled differently on the two databases this has to run on; the
# table is small and this runs once.
BACKFILL = sa.text("""
    UPDATE section_versions
    SET seq = (
        SELECT COUNT(*)
        FROM section_versions AS earlier
        WHERE earlier.user_id = section_versions.user_id
          AND (
            earlier.created_at < section_versions.created_at
            OR (
              earlier.created_at = section_versions.created_at
              AND earlier.id <= section_versions.id
            )
          )
    )
""")


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # SQLite stores this column as plain text and needs nothing. Postgres
        # has a real enum type, and a value has to be added to it before a row
        # can carry one. Allowed inside a transaction since Postgres 12, as
        # long as the new value is not used in the same one — it is not.
        op.execute("ALTER TYPE section_version_type ADD VALUE IF NOT EXISTS 'resume'")

    # nullable first: the column is NOT NULL in the end, but existing rows have
    # no value until the backfill below has run
    op.add_column("section_versions", sa.Column("seq", sa.Integer(), nullable=True))
    op.execute(BACKFILL)

    with op.batch_alter_table("section_versions") as batch:
        batch.alter_column("seq", existing_type=sa.Integer(), nullable=False)
        batch.create_index("ix_section_versions_seq", ["seq"], unique=False)
        batch.create_unique_constraint(
            "uq_section_versions_user_seq", ["user_id", "seq"]
        )


def downgrade() -> None:
    with op.batch_alter_table("section_versions") as batch:
        batch.drop_constraint("uq_section_versions_user_seq", type_="unique")
        batch.drop_index("ix_section_versions_seq")
        batch.drop_column("seq")

    # The enum value stays. Postgres cannot remove one, and a history row that
    # already names it would become unreadable if it could.

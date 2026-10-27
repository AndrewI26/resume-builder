"""skill lists carry a nickname

A skill list's name is the label printed on the resume, so two lists that
both print as "Languages" could not be told apart in the library. An
optional nickname names the list for its owner alone.

Revision ID: f2b6d8a1c3e5
Revises: d7a3c5e9f1b2
Create Date: 2026-10-27

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2b6d8a1c3e5"
down_revision: str | Sequence[str] | None = "d7a3c5e9f1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("nickname", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("skills", "nickname")

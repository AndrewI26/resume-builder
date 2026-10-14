"""educations list related coursework

An optional, ordered list of course names under each education. Existing rows
start with none.

Revision ID: d7a3c5e9f1b2
Revises: c4f1a9e2d6b8
Create Date: 2026-10-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d7a3c5e9f1b2"
down_revision: str | Sequence[str] | None = "c4f1a9e2d6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "educations",
        sa.Column(
            "coursework",
            postgresql.ARRAY(sa.String(length=255)),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("educations", "coursework")

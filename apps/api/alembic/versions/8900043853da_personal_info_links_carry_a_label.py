"""personal info links carry a label

github/linkedin/portfolio become {url, label} objects instead of bare URL
strings, so a resume can show "My GitHub" instead of the raw link. Existing
values are wrapped with an empty label rather than discarded.

Revision ID: 8900043853da
Revises: a1f4c7b2e930
Create Date: 2026-08-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8900043853da"
down_revision: str | Sequence[str] | None = "a1f4c7b2e930"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LINK_COLUMNS = ("github", "linkedin", "portfolio")


def upgrade() -> None:
    for column in LINK_COLUMNS:
        op.alter_column(
            "personal_info",
            column,
            type_=postgresql.JSONB(astext_type=sa.Text()),
            postgresql_using=(
                f"CASE WHEN {column} IS NULL THEN NULL "
                f"ELSE jsonb_build_object('url', {column}, 'label', NULL) END"
            ),
        )


def downgrade() -> None:
    for column in LINK_COLUMNS:
        op.alter_column(
            "personal_info",
            column,
            type_=sa.String(length=2048),
            postgresql_using=f"{column}->>'url'",
        )

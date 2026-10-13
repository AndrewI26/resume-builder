"""projects carry a github link

A project keeps its own link (the live site, a store page) and gains an
optional link to its repository, so a resume can show both. Links that
already point at GitHub were repositories all along, so they move across.

Revision ID: b3e8d2f41c07
Revises: e9aba937a34b
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3e8d2f41c07"
down_revision: str | Sequence[str] | None = "e9aba937a34b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# the host, with or without a scheme or www
GITHUB_LINK = """(
    lower(link) LIKE 'https://github.com/%'
    OR lower(link) LIKE 'http://github.com/%'
    OR lower(link) LIKE 'https://www.github.com/%'
    OR lower(link) LIKE 'http://www.github.com/%'
    OR lower(link) LIKE 'github.com/%'
    OR lower(link) LIKE 'www.github.com/%'
)"""


def upgrade() -> None:
    op.add_column("projects", sa.Column("github", sa.String(length=2048), nullable=True))
    op.execute(f"UPDATE projects SET github = link, link = NULL WHERE {GITHUB_LINK}")


def downgrade() -> None:
    # a project with both keeps its own link; the repository has nowhere to go
    op.execute("UPDATE projects SET link = github WHERE link IS NULL")
    op.drop_column("projects", "github")

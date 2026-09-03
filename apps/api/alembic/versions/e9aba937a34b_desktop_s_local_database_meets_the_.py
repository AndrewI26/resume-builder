"""desktop's local database meets the postgres job queue

Revision ID: e9aba937a34b
Revises: 72e148f55704, 78d817c69cb8
Create Date: 2026-09-03 13:43:35.202648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9aba937a34b'
down_revision: Union[str, Sequence[str], None] = ('72e148f55704', '78d817c69cb8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

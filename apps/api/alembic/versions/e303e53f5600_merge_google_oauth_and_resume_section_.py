"""merge google oauth and resume section heads

Revision ID: e303e53f5600
Revises: 9c4e17b0a5d2, d83dad4c5f97
Create Date: 2026-08-09 22:16:50.684020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e303e53f5600'
down_revision: Union[str, Sequence[str], None] = ('9c4e17b0a5d2', 'd83dad4c5f97')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

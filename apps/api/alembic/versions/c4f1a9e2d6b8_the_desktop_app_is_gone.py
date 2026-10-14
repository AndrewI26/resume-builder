"""the desktop app is gone

Syncing a desktop library with an account was the only reason for the sync
state, agreements and conflicts, and nothing writes them any more. The change
history stays: import and export still record into it.

Revision ID: c4f1a9e2d6b8
Revises: b3e8d2f41c07
Create Date: 2026-10-14

"""

import importlib.util
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "c4f1a9e2d6b8"
down_revision: str | Sequence[str] | None = "b3e8d2f41c07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_sync_state_user_id"), table_name="sync_state")
    op.drop_table("sync_state")
    op.drop_index(op.f("ix_sync_conflicts_user_id"), table_name="sync_conflicts")
    op.drop_table("sync_conflicts")
    op.drop_index(op.f("ix_sync_agreements_user_id"), table_name="sync_agreements")
    op.drop_index(op.f("ix_sync_agreements_record_id"), table_name="sync_agreements")
    op.drop_table("sync_agreements")


def downgrade() -> None:
    # the revision that first made these tables already knows how; a module
    # name starting with a digit cannot be imported the ordinary way
    path = Path(__file__).with_name(
        "78d817c69cb8_a_local_database_remembers_its_account.py"
    )
    spec = importlib.util.spec_from_file_location("_sync_tables", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()

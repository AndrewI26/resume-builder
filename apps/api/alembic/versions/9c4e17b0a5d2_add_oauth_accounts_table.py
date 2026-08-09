"""add oauth accounts table

Revision ID: 9c4e17b0a5d2
Revises: 1d5b17e3028f
Create Date: 2026-08-09 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4e17b0a5d2"
down_revision: str | Sequence[str] | None = "1d5b17e3028f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_accounts_provider_account"
        ),
    )
    op.create_index(
        op.f("ix_oauth_accounts_user_id"), "oauth_accounts", ["user_id"], unique=False
    )

    # users created through Google never set a password
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.VARCHAR(length=255),
        nullable=True,
    )

    # display name, populated from the provider's profile where we have one
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "name")

    # rows without a password cannot exist in the pre-migration schema
    op.execute("DELETE FROM users WHERE hashed_password IS NULL")
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )

    op.drop_index(op.f("ix_oauth_accounts_user_id"), table_name="oauth_accounts")
    op.drop_table("oauth_accounts")

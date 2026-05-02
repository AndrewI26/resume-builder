"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "basics_sections",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("variant_name", sa.String(100), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200)),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("linkedin_text", sa.String(200)),
        sa.Column("github_url", sa.String(500)),
        sa.Column("github_text", sa.String(200)),
        sa.Column("website_url", sa.String(500)),
        sa.Column("website_text", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "skills_sections",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("variant_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "skill_categories",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("skills_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("items", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "experience_sections",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("variant_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "experience_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("experience_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.String(300), nullable=False),
        sa.Column("company_url", sa.String(500)),
        sa.Column("role", sa.String(300), nullable=False),
        sa.Column("date_range", sa.String(100), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "experience_highlights",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("experience_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "projects_sections",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("variant_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "project_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("url", sa.String(500)),
        sa.Column("tech_stack", sa.String(500)),
        sa.Column("date_range", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "project_highlights",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("project_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "education_sections",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("variant_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "education_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("education_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution", sa.String(300), nullable=False),
        sa.Column("program", sa.String(300), nullable=False),
        sa.Column("date_range", sa.String(100), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "education_awards",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("education_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("column", sa.Enum("left", "right", name="awardcolumn"), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("basics_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("basics_sections.id"), nullable=False),
        sa.Column("skills_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("skills_sections.id")),
        sa.Column("experience_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("experience_sections.id")),
        sa.Column("projects_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects_sections.id")),
        sa.Column("education_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("education_sections.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("resumes")
    op.drop_table("education_awards")
    op.drop_table("education_items")
    op.drop_table("education_sections")
    op.drop_table("project_highlights")
    op.drop_table("project_items")
    op.drop_table("projects_sections")
    op.drop_table("experience_highlights")
    op.drop_table("experience_items")
    op.drop_table("experience_sections")
    op.drop_table("skill_categories")
    op.drop_table("skills_sections")
    op.drop_table("basics_sections")
    op.execute("DROP TYPE IF EXISTS awardcolumn")

"""resume sections carry type and order

Replaces the resumes.sections UUID array with a resume_sections join table.

The array stored bare ids, so nothing recorded whether a given id was a
project or an education, and nothing recorded where a block should sit. The
renderer needs both. Ids are globally unique, so the type is recoverable by
asking each section table in turn — which is what the data migration below
does, rather than dropping rows that already exist.

Revision ID: a1f4c7b2e930
Revises: 2cfdb4789329
Create Date: 2026-08-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1f4c7b2e930"
down_revision: str | Sequence[str] | None = "2cfdb4789329"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECTION_TABLES = {
    "education": "educations",
    "experience": "expirences",
    "project": "projects",
    "skill": "skills",
}

# The order Jake's template lays sections out in.
DEFAULT_SECTION_ORDER = "{skill,experience,project,education}"


def upgrade() -> None:
    section_type = postgresql.ENUM(
        *SECTION_TABLES, name="resume_section_type", create_type=False
    )
    section_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "resume_sections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column("section_type", section_type, nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resume_id",
            "section_type",
            "section_id",
            name="uq_resume_sections_resume_section",
        ),
    )
    op.create_index(
        op.f("ix_resume_sections_resume_id"),
        "resume_sections",
        ["resume_id"],
        unique=False,
    )

    op.add_column("resumes", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("resumes", sa.Column("template", sa.String(length=50), nullable=True))
    op.add_column(
        "resumes", sa.Column("full_name", sa.String(length=255), nullable=True)
    )
    op.add_column("resumes", sa.Column("personal_info_id", sa.UUID(), nullable=True))
    op.add_column(
        "resumes",
        sa.Column("section_order", postgresql.ARRAY(sa.String(length=50)), nullable=True),
    )
    op.create_foreign_key(
        "fk_resumes_personal_info_id",
        "resumes",
        "personal_info",
        ["personal_info_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # carry existing rows across before the old column goes
    op.execute("UPDATE resumes SET title = name WHERE title IS NULL")
    op.execute("UPDATE resumes SET template = 'jakes' WHERE template IS NULL")
    op.execute(
        f"UPDATE resumes SET section_order = '{DEFAULT_SECTION_ORDER}'"
        " WHERE section_order IS NULL"
    )

    # Recover each id's type by asking every section table, then number the
    # ids within their type in the order the array listed them.
    lookup = " UNION ALL ".join(
        f"SELECT id, '{label}'::resume_section_type AS section_type FROM {table}"
        for label, table in SECTION_TABLES.items()
    )
    op.execute(f"""
        INSERT INTO resume_sections
            (id, resume_id, section_type, section_id, position, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            listed.resume_id,
            owner.section_type,
            listed.section_id,
            (row_number() OVER (
                PARTITION BY listed.resume_id, owner.section_type
                ORDER BY listed.ordinality
            ) - 1)::int,
            now(),
            now()
        FROM (
            SELECT r.id AS resume_id, s.section_id, s.ordinality
            FROM resumes r
            CROSS JOIN LATERAL unnest(r.sections)
                WITH ORDINALITY AS s(section_id, ordinality)
        ) AS listed
        JOIN ({lookup}) AS owner ON owner.id = listed.section_id
    """)

    op.alter_column("resumes", "title", nullable=False)
    op.alter_column("resumes", "template", nullable=False)
    op.alter_column("resumes", "section_order", nullable=False)

    op.drop_column("resumes", "sections")
    op.drop_column("resumes", "name")


def downgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column("name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "resumes",
        sa.Column("sections", postgresql.ARRAY(sa.UUID()), nullable=True),
    )

    op.execute("UPDATE resumes SET name = title WHERE name IS NULL")
    # the type is dropped on the way back, since the array cannot express it
    op.execute("""
        UPDATE resumes r
        SET sections = COALESCE((
            SELECT array_agg(rs.section_id ORDER BY rs.section_type, rs.position)
            FROM resume_sections rs
            WHERE rs.resume_id = r.id
        ), '{}'::uuid[])
    """)

    op.alter_column("resumes", "name", nullable=False)
    op.alter_column("resumes", "sections", nullable=False)

    op.drop_constraint("fk_resumes_personal_info_id", "resumes", type_="foreignkey")
    for column in ("section_order", "personal_info_id", "full_name", "template", "title"):
        op.drop_column("resumes", column)

    op.drop_index(op.f("ix_resume_sections_resume_id"), table_name="resume_sections")
    op.drop_table("resume_sections")
    sa.Enum(name="resume_section_type").drop(op.get_bind())

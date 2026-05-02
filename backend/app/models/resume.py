import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------

class BasicsSection(Base):
    __tablename__ = "basics_sections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    linkedin_text: Mapped[str | None] = mapped_column(String(200))
    github_url: Mapped[str | None] = mapped_column(String(500))
    github_text: Mapped[str | None] = mapped_column(String(200))
    website_url: Mapped[str | None] = mapped_column(String(500))
    website_text: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    resumes: Mapped[list["Resume"]] = relationship(back_populates="basics")


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

class SkillsSection(Base):
    __tablename__ = "skills_sections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    categories: Mapped[list["SkillCategory"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="SkillCategory.sort_order"
    )
    resumes: Mapped[list["Resume"]] = relationship(back_populates="skills")


class SkillCategory(Base):
    __tablename__ = "skill_categories"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("skills_sections.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    items: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped["SkillsSection"] = relationship(back_populates="categories")


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------

class ExperienceSection(Base):
    __tablename__ = "experience_sections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    items: Mapped[list["ExperienceItem"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="ExperienceItem.sort_order"
    )
    resumes: Mapped[list["Resume"]] = relationship(back_populates="experience")


class ExperienceItem(Base):
    __tablename__ = "experience_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("experience_sections.id", ondelete="CASCADE"), nullable=False)
    company: Mapped[str] = mapped_column(String(300), nullable=False)
    company_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(300), nullable=False)
    date_range: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped["ExperienceSection"] = relationship(back_populates="items")
    highlights: Mapped[list["ExperienceHighlight"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ExperienceHighlight.sort_order"
    )


class ExperienceHighlight(Base):
    __tablename__ = "experience_highlights"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("experience_items.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped["ExperienceItem"] = relationship(back_populates="highlights")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class ProjectsSection(Base):
    __tablename__ = "projects_sections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    items: Mapped[list["ProjectItem"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="ProjectItem.sort_order"
    )
    resumes: Mapped[list["Resume"]] = relationship(back_populates="projects")


class ProjectItem(Base):
    __tablename__ = "project_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects_sections.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    tech_stack: Mapped[str | None] = mapped_column(String(500))
    date_range: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped["ProjectsSection"] = relationship(back_populates="items")
    highlights: Mapped[list["ProjectHighlight"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ProjectHighlight.sort_order"
    )


class ProjectHighlight(Base):
    __tablename__ = "project_highlights"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("project_items.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped["ProjectItem"] = relationship(back_populates="highlights")


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

class EducationSection(Base):
    __tablename__ = "education_sections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    items: Mapped[list["EducationItem"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="EducationItem.sort_order"
    )
    resumes: Mapped[list["Resume"]] = relationship(back_populates="education")


class EducationItem(Base):
    __tablename__ = "education_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("education_sections.id", ondelete="CASCADE"), nullable=False)
    institution: Mapped[str] = mapped_column(String(300), nullable=False)
    program: Mapped[str] = mapped_column(String(300), nullable=False)
    date_range: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped["EducationSection"] = relationship(back_populates="items")
    awards: Mapped[list["EducationAward"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="EducationAward.sort_order"
    )


class AwardColumn(PyEnum):
    left = "left"
    right = "right"


class EducationAward(Base):
    __tablename__ = "education_awards"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("education_items.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    column: Mapped[AwardColumn] = mapped_column(Enum(AwardColumn), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped["EducationItem"] = relationship(back_populates="awards")


# ---------------------------------------------------------------------------
# Resume (assembles one variant from each section)
# ---------------------------------------------------------------------------

class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    basics_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("basics_sections.id"), nullable=False)
    skills_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("skills_sections.id"))
    experience_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("experience_sections.id"))
    projects_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("projects_sections.id"))
    education_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("education_sections.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    basics: Mapped["BasicsSection"] = relationship(back_populates="resumes")
    skills: Mapped["SkillsSection | None"] = relationship(back_populates="resumes")
    experience: Mapped["ExperienceSection | None"] = relationship(back_populates="resumes")
    projects: Mapped["ProjectsSection | None"] = relationship(back_populates="resumes")
    education: Mapped["EducationSection | None"] = relationship(back_populates="resumes")

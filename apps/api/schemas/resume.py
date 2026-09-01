from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from enums import DEFAULT_SECTION_ORDER, ResumeSectionType
from schemas.education import EducationRead
from schemas.expirence import ExpirenceRead
from schemas.personal_info import PersonalInfoRead
from schemas.project import ProjectRead
from schemas.skill import SkillRead

SectionOrder = list[ResumeSectionType]


def _reject_duplicates(order: SectionOrder) -> SectionOrder:
    if len(set(order)) != len(order):
        raise ValueError("section_order cannot repeat a section type")

    return order


class ResumeBase(BaseModel):
    title: str = Field(max_length=255)
    template: str = Field(default="jakes", max_length=50)

    full_name: str | None = Field(default=None, max_length=255)
    personal_info_id: UUID | None = None

    section_order: SectionOrder = Field(
        default_factory=lambda: list(DEFAULT_SECTION_ORDER)
    )

    _no_duplicates = field_validator("section_order")(_reject_duplicates)


class ResumeSectionRef(BaseModel):
    """A pointer to one of the caller's sections, by type and id."""

    section_type: ResumeSectionType
    section_id: UUID


class ResumeCreate(ResumeBase):
    """A new resume. Everything but the title has a usable default.

    Sections may be attached here rather than in a second call, because the
    editor builds a resume and its contents in one modal and there is no
    reason to make it save twice.
    """

    sections: list[ResumeSectionRef] = []


class ResumeEdit(ResumeBase):
    """The full representation a replace has to send."""


class ResumeRead(ResumeBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    updated_at: datetime


class ResumeSectionsReplace(BaseModel):
    """The whole membership list at once.

    Position is the index within the run of entries sharing a type, so
    reordering is a rewrite of the list rather than a separate operation —
    the same trade the skill lists make.
    """

    sections: list[ResumeSectionRef]

    @field_validator("sections")
    @classmethod
    def validate_unique(
        cls, sections: list[ResumeSectionRef]
    ) -> list[ResumeSectionRef]:
        seen = {(ref.section_type, ref.section_id) for ref in sections}
        if len(seen) != len(sections):
            raise ValueError("a section cannot be listed twice")

        return sections


class EducationBlock(BaseModel):
    type: Literal[ResumeSectionType.EDUCATION] = ResumeSectionType.EDUCATION
    items: list[EducationRead]


class ExperienceBlock(BaseModel):
    type: Literal[ResumeSectionType.EXPERIENCE] = ResumeSectionType.EXPERIENCE
    items: list[ExpirenceRead]


class ProjectBlock(BaseModel):
    type: Literal[ResumeSectionType.PROJECT] = ResumeSectionType.PROJECT
    items: list[ProjectRead]


class SkillBlock(BaseModel):
    type: Literal[ResumeSectionType.SKILL] = ResumeSectionType.SKILL
    items: list[SkillRead]


SectionBlock = Annotated[
    EducationBlock | ExperienceBlock | ProjectBlock | SkillBlock,
    Field(discriminator="type"),
]


class ResumeDocument(BaseModel):
    """Everything a renderer needs, resolved and in order, in one response.

    Bullet points are hydrated and blocks arrive in ``section_order``, so a
    client can walk the structure straight into a template without a second
    request or any sorting of its own. Blocks with no items are dropped, since
    an empty section would otherwise render as a bare heading.
    """

    id: UUID
    title: str
    template: str

    # already resolved against the user's display name; empty when neither the
    # resume nor the account carries one
    full_name: str

    personal_info: PersonalInfoRead | None = None
    sections: list[SectionBlock]

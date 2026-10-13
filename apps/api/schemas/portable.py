"""The library as one portable JSON document, for import and export.

A person, or whatever tool they used, writes their sections and resumes into a
single file, and import creates all of it at once. Nothing in it is a database
id: a resume names the sections it contains by ``key``, a string the file's
author chose, so a file can be written from scratch without asking the API
for anything first. Export writes the same shape, using each record's id as
its key, which makes a backup and a hand-written file the same kind of thing.

The checks here are deliberately strict — unknown fields are refused rather
than dropped — because the usual author is a model that was handed this schema,
and a typo it made should come back as an error instead of quietly vanishing.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from enums import DEFAULT_SECTION_ORDER, ResumeSectionType
from schemas.project import Technology
from schemas.resume import SectionOrder, _reject_duplicates
from schemas.skill import SkillItem

# Enough for any real library, and a ceiling on what one request can write.
MAX_ITEMS = 200
MAX_RESUMES = 50
MAX_BULLETS = 50
MAX_LIST_ENTRIES = 100

Key = Annotated[str, Field(min_length=1, max_length=255)]
BulletText = Annotated[str, Field(min_length=1, max_length=1000)]
Text = Annotated[str, Field(max_length=255)]
Url = Annotated[str, Field(max_length=2048)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PortableLink(_Strict):
    url: Url
    label: Text | None = None


class PortablePersonalInfo(_Strict):
    key: Key | None = None

    email: Text | None = None
    phone_number: Annotated[str, Field(max_length=50)] | None = None
    address: Text | None = None

    github: PortableLink | None = None
    linkedin: PortableLink | None = None
    portfolio: PortableLink | None = None


class PortableEducation(_Strict):
    key: Key | None = None

    name: Text
    subheading: Text
    duration: Text
    location: Text


class PortableExperience(_Strict):
    key: Key | None = None

    company: Text
    position: Text
    duration: Text
    location: Text

    bullet_points: list[BulletText] = Field(default=[], max_length=MAX_BULLETS)


class PortableProject(_Strict):
    key: Key | None = None

    name: Text
    link: Url | None = None
    github: Url | None = None

    technologies: list[Technology] = Field(default=[], max_length=MAX_LIST_ENTRIES)
    bullet_points: list[BulletText] = Field(default=[], max_length=MAX_BULLETS)


class PortableSkill(_Strict):
    key: Key | None = None

    name: Text
    items: list[SkillItem] = Field(default=[], max_length=MAX_LIST_ENTRIES)


class PortableResume(_Strict):
    title: Text
    template: Annotated[str, Field(max_length=50)] = "jakes"
    full_name: Text | None = None

    # the key of an entry in the file's personal_info list
    personal_info: Key | None = None

    section_order: SectionOrder = Field(
        default_factory=lambda: list(DEFAULT_SECTION_ORDER)
    )
    # keys of entries in the file's lists, in the order the resume shows them
    sections: dict[ResumeSectionType, list[Key]] = {}

    _no_duplicates = field_validator("section_order")(_reject_duplicates)

    @field_validator("sections")
    @classmethod
    def _no_repeated_keys(
        cls, sections: dict[ResumeSectionType, list[str]]
    ) -> dict[ResumeSectionType, list[str]]:
        for section_type, keys in sections.items():
            if len(set(keys)) != len(keys):
                raise ValueError(f"{section_type.value} lists a key more than once")
        return sections


# which of the file's lists a resume's ``sections[type]`` keys point into
LIST_NAMES = {
    ResumeSectionType.EDUCATION: "education",
    ResumeSectionType.EXPERIENCE: "experience",
    ResumeSectionType.PROJECT: "projects",
    ResumeSectionType.SKILL: "skills",
}


class PortableLibrary(_Strict):
    """A whole library: sections, and resumes made from them."""

    format: Literal["resume-builder"] = "resume-builder"
    version: Literal[1] = 1

    personal_info: list[PortablePersonalInfo] = Field(default=[], max_length=MAX_ITEMS)
    education: list[PortableEducation] = Field(default=[], max_length=MAX_ITEMS)
    experience: list[PortableExperience] = Field(default=[], max_length=MAX_ITEMS)
    projects: list[PortableProject] = Field(default=[], max_length=MAX_ITEMS)
    skills: list[PortableSkill] = Field(default=[], max_length=MAX_ITEMS)
    resumes: list[PortableResume] = Field(default=[], max_length=MAX_RESUMES)

    def keys_of(self, list_name: str) -> list[str | None]:
        items: list[
            PortablePersonalInfo
            | PortableEducation
            | PortableExperience
            | PortableProject
            | PortableSkill
        ] = getattr(self, list_name)
        return [item.key for item in items]

    @model_validator(mode="after")
    def _references_resolve(self) -> "PortableLibrary":
        """Keys are unique within a list, and every key a resume names exists.

        Every problem is reported at once, each starting with where it is, so
        whoever wrote the file can fix them all in one pass.
        """
        problems: list[str] = []
        available: dict[str, set[str]] = {}

        for list_name in ("personal_info", *LIST_NAMES.values()):
            seen: set[str] = set()
            for index, key in enumerate(self.keys_of(list_name)):
                if key is None:
                    continue
                if key in seen:
                    problems.append(f"{list_name}[{index}].key: {key!r} is used twice")
                seen.add(key)
            available[list_name] = seen

        for index, resume in enumerate(self.resumes):
            where = f"resumes[{index}]"
            if (
                resume.personal_info is not None
                and resume.personal_info not in available["personal_info"]
            ):
                problems.append(
                    f"{where}.personal_info: no personal_info entry has key "
                    f"{resume.personal_info!r}"
                )

            for section_type, keys in resume.sections.items():
                list_name = LIST_NAMES[section_type]
                for position, key in enumerate(keys):
                    if key not in available[list_name]:
                        problems.append(
                            f"{where}.sections.{section_type.value}[{position}]: "
                            f"no {list_name} entry has key {key!r}"
                        )

        if problems:
            raise ValueError("; ".join(problems))

        return self


class ImportedResume(BaseModel):
    id: UUID
    title: str


class ImportSummary(BaseModel):
    """What an import created, or on a dry run would have created."""

    dry_run: bool

    personal_info: int
    education: int
    experience: int
    projects: int
    skills: int
    resumes: list[ImportedResume]

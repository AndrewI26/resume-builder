"""A library's sections as one portable JSON document, for import and export.

A person, or whatever tool they used, writes their sections into a single
file, and import adds all of them at once. Resumes are not part of it: they
are built in the app from whichever sections a person picks, and a file only
has to say what those sections are. Export writes the same shape, so a backup
and a hand-written file are the same kind of thing.

The checks are deliberately strict — unknown fields are refused rather than
dropped — because the usual author is a model that was handed this schema, and
a typo it made should come back as an error instead of quietly vanishing.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from schemas.project import Technology
from schemas.skill import SkillItem

# Enough for any real library, and a ceiling on what one request can write.
MAX_ITEMS = 200
MAX_BULLETS = 50
MAX_LIST_ENTRIES = 100

BulletText = Annotated[str, Field(min_length=1, max_length=1000)]
Text = Annotated[str, Field(max_length=255)]
Url = Annotated[str, Field(max_length=2048)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PortableLink(_Strict):
    url: Url
    label: Text | None = None


class PortablePersonalInfo(_Strict):
    email: Text | None = None
    phone_number: Annotated[str, Field(max_length=50)] | None = None
    address: Text | None = None

    github: PortableLink | None = None
    linkedin: PortableLink | None = None
    portfolio: PortableLink | None = None


class PortableEducation(_Strict):
    name: Text
    subheading: Text
    duration: Text
    location: Text

    coursework: list[Text] = Field(default=[], max_length=MAX_LIST_ENTRIES)


class PortableExperience(_Strict):
    company: Text
    position: Text
    duration: Text
    location: Text

    bullet_points: list[BulletText] = Field(default=[], max_length=MAX_BULLETS)


class PortableProject(_Strict):
    name: Text
    link: Url | None = None
    github: Url | None = None

    technologies: list[Technology] = Field(default=[], max_length=MAX_LIST_ENTRIES)
    bullet_points: list[BulletText] = Field(default=[], max_length=MAX_BULLETS)


class PortableSkill(_Strict):
    name: Text
    items: list[SkillItem] = Field(default=[], max_length=MAX_LIST_ENTRIES)


class PortableLibrary(_Strict):
    """Every kind of section, each list optional."""

    personal_info: list[PortablePersonalInfo] = Field(default=[], max_length=MAX_ITEMS)
    education: list[PortableEducation] = Field(default=[], max_length=MAX_ITEMS)
    experience: list[PortableExperience] = Field(default=[], max_length=MAX_ITEMS)
    projects: list[PortableProject] = Field(default=[], max_length=MAX_ITEMS)
    skills: list[PortableSkill] = Field(default=[], max_length=MAX_ITEMS)


class ImportSummary(BaseModel):
    """What an import added, or on a dry run would have added."""

    dry_run: bool

    personal_info: int
    education: int
    experience: int
    projects: int
    skills: int

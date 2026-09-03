import enum


class SectionType(str, enum.Enum):
    """The kinds of record that carry version history.

    Mostly section kinds, plus the resume itself — a resume is not a section of
    anything, but it is a thing a person edits and therefore a thing that has
    to be carried between a desktop and an account, in the same order as
    everything else. One history is what lets a sync read a user's changes as a
    single sequence rather than merging several.

    The member values are the stored labels in both Postgres and JSON: the
    column passes ``db.enum_values`` to ``values_callable`` so the type's
    labels are these rather than the member names, and Pydantic serializes a
    ``str`` enum by its value. Adding a member therefore changes the API
    contract and the database type together.
    """

    EDUCATION = "education"
    EXPERIENCE = "experience"
    PERSONAL_INFO = "personal_info"
    PROJECT = "project"
    SKILL = "skill"
    RESUME = "resume"


class OperationType(str, enum.Enum):
    """What a version snapshot records the section as having undergone."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ResumeSectionType(str, enum.Enum):
    """The section kinds a resume orders and renders as headed blocks.

    Deliberately narrower than ``SectionType``: personal info is the header of
    a resume rather than one of its sections, so it hangs off ``Resume``
    directly and cannot be expressed here.
    """

    EDUCATION = "education"
    EXPERIENCE = "experience"
    PROJECT = "project"
    SKILL = "skill"


# The order Jake's template lays sections out in, used for a new resume.
DEFAULT_SECTION_ORDER = [
    ResumeSectionType.SKILL,
    ResumeSectionType.EXPERIENCE,
    ResumeSectionType.PROJECT,
    ResumeSectionType.EDUCATION,
]

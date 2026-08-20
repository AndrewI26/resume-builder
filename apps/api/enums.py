import enum


class SectionType(str, enum.Enum):
    """The resume section kinds that carry version history.

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


class OperationType(str, enum.Enum):
    """What a version snapshot records the section as having undergone."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

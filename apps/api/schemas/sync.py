"""What crosses between a desktop and an account."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from enums import OperationType, SectionType


class Change(BaseModel):
    """One thing that happened to one record.

    The snapshot is the record as it stood, not a pointer to it, which is what
    lets a delete be transferred at all: by the time anyone asks, the row it
    describes is gone.
    """

    record_type: SectionType
    record_id: UUID
    version: int
    operation: OperationType
    snapshot: dict[str, Any]

    # this record's place in the caller's single ordering; the client stores
    # the last one it applied and asks for what came after
    seq: int


class ChangeFeed(BaseModel):
    """A page of history, oldest first."""

    changes: list[Change]

    #: The sequence number to ask from next time. Unchanged from ``since`` when
    #: there was nothing new, so a client that stores it is always correct.
    cursor: int

    #: Whether stopping here was the page limit rather than the end of the
    #: history. A client that ignores this stops halfway and believes it is up
    #: to date, so it is stated rather than implied by a full page.
    more: bool


class PullQuery(BaseModel):
    since: int = Field(default=0, ge=0)
    limit: int = Field(default=500, ge=1, le=2000)


class PushChange(BaseModel):
    """A change made elsewhere, offered to this database.

    ``base_version`` is the version of this record the client last agreed with
    the server. It is the whole of conflict detection: if the server has moved
    past it, somebody else changed the same record in the meantime and nobody
    but a person can say which of the two was meant.

    ``None`` means "I believe you have never seen this record" — a record
    created offline. It is checked rather than trusted, so claiming it for a
    record the server does know about is a conflict like any other.
    """

    record_type: SectionType
    record_id: UUID
    base_version: int | None = None
    operation: OperationType
    snapshot: dict[str, Any] = Field(default_factory=dict)


class PushOutcome(str, Enum):
    APPLIED = "applied"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class PushResult(BaseModel):
    """What became of one offered change."""

    record_id: UUID
    record_type: SectionType
    outcome: PushOutcome

    #: The version the record now has here. Set when applied, so the client can
    #: record what it has agreed to without pulling its own write back.
    version: int | None = None

    #: Where the applied change sits in the caller's history, so a client can
    #: advance its cursor past its own writes rather than replaying them.
    seq: int | None = None

    #: What the server has instead, when the two disagree. This is the other
    #: side of the prompt a person is shown.
    theirs: Change | None = None

    #: Why it was refused, when it was.
    reason: str | None = None


class PushRequest(BaseModel):
    changes: list[PushChange]


class PushResponse(BaseModel):
    results: list[PushResult]

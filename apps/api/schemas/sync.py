"""What crosses between a desktop and an account."""

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

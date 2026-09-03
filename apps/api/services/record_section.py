"""Writing to the history every change goes into.

The history is what a sync reads. A desktop that has been offline asks for
everything after the last sequence number it saw, and gets each change in the
order it happened, with the snapshot of what the record looked like — including
for records that have since been deleted, which is why the log holds copies
rather than pointers.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.section_version import SectionVersion

# How many times to redo work whose sequence number someone else took first.
# Two requests from the same person at the same instant is already unusual;
# three collisions in a row is not something to keep trying through.
MAX_ATTEMPTS = 3


def _next_version(db: Session, section_id: UUID) -> int:
    """This record's next place in its own history."""
    latest = db.scalar(
        select(func.max(SectionVersion.version)).where(
            SectionVersion.section_id == section_id
        )
    )
    return (latest or 0) + 1


def _next_seq(db: Session, user_id: UUID) -> int:
    """The next place in this user's single ordering of everything."""
    latest = db.scalar(
        select(func.max(SectionVersion.seq)).where(SectionVersion.user_id == user_id)
    )
    return (latest or 0) + 1


def stage_version(
    db: Session,
    user_id: UUID,
    section_type: SectionType,
    section_id: UUID,
    operation: OperationType,
    snapshot: dict[str, Any],
) -> SectionVersion:
    """Add a history entry to the session without committing it.

    For callers that are writing the record itself in the same transaction and
    need the two to land together or not at all. They own the retry, because
    retrying only this half would record a change that never happened to the
    data — see ``record_version``, which may only retry because it is the whole
    of its own transaction.
    """
    section_version = SectionVersion(
        user_id=user_id,
        section_type=section_type,
        section_id=section_id,
        version=_next_version(db, section_id),
        seq=_next_seq(db, user_id),
        operation=operation,
        snapshot=snapshot,
    )
    db.add(section_version)
    return section_version


def record_version(
    db: Session,
    user_id: UUID,
    section_type: SectionType,
    section_id: UUID,
    operation: OperationType,
    snapshot: dict[str, Any],
) -> SectionVersion:
    """Record what just happened to a record, and return the entry.

    The routers call this after their own commit, so the only thing pending is
    the entry itself and rolling back to retry costs nothing else.

    Both counters are read and written without a lock, which two requests
    arriving together could get away with — SQLite has no ``FOR UPDATE`` and
    the desktop has no concurrency to speak of, so a unique constraint and a
    retry is the portable way to be sure rather than the cheap one. The
    constraint is what makes this correct; the retry only makes it quiet.
    """
    for attempt in range(MAX_ATTEMPTS):
        section_version = stage_version(
            db, user_id, section_type, section_id, operation, snapshot
        )

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                raise
            continue

        return section_version

    # unreachable: the loop either returns or raises on its last attempt
    raise AssertionError("record_version fell out of its retry loop")

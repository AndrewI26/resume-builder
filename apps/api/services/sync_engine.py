"""Reconciling this database with an account.

Runs in the desktop's own API rather than in its window, for two reasons. The
window is not served over http and so has no origin the hosted API would accept
from a browser; and applying a change from the account is exactly what
``sync_apply`` already does for a change pushed from anywhere else, so doing it
here reuses that instead of writing it a second time in another language.

The shape of a sync
-------------------
Pull first, then push. Taking the account's changes before offering ours means
a record changed on both sides is noticed while both versions are still in
front of us, rather than after ours has already overwritten theirs.

Each record carries two version numbers, because each side counts its own
history. ``SyncAgreement`` remembers the pair the two sides last shared. A side
whose current version has moved past the agreed one has changed since; when
both have, nobody but a person can say which was meant, so it is recorded as a
conflict and left alone. Nothing is merged and nothing is overwritten — the
record keeps whatever it had here until the choice is made.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.section_version import SectionVersion
from models.sync_state import SyncAgreement, SyncConflict, SyncState
from services.record_section import stage_version
from services.sync_apply import UnapplicableChange, apply_delete, apply_snapshot


class Cloud(Protocol):
    """The account, as much of it as syncing needs.

    A protocol rather than a concrete client so a test can be the account
    instead of standing up a second server on a port.
    """

    def pull(self, since: int, limit: int) -> dict[str, Any]: ...

    def push(self, changes: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass
class SyncReport:
    """What one run did, in the terms the window reports to a person."""

    pulled: int = 0
    pushed: int = 0
    conflicts: list[UUID] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    @property
    def had_conflicts(self) -> bool:
        return bool(self.conflicts)


def _agreements(db: Session, user_id: UUID) -> dict[UUID, SyncAgreement]:
    rows = db.scalars(
        select(SyncAgreement).where(SyncAgreement.user_id == user_id)
    ).all()
    return {row.record_id: row for row in rows}


def _agree(
    db: Session,
    user_id: UUID,
    record_id: UUID,
    record_type: SectionType,
    local_version: int,
    cloud_version: int,
    known: dict[UUID, SyncAgreement],
) -> None:
    """Record that both sides now hold the same thing."""
    existing = known.get(record_id)
    if existing is None:
        existing = SyncAgreement(
            user_id=user_id,
            record_id=record_id,
            record_type=record_type,
            local_version=local_version,
            cloud_version=cloud_version,
        )
        db.add(existing)
        known[record_id] = existing
        return

    existing.local_version = local_version
    existing.cloud_version = cloud_version


def _local_version(db: Session, user_id: UUID, record_id: UUID) -> int:
    """How many times this database has changed a record. Zero if never."""
    latest = db.scalar(
        select(func.max(SectionVersion.version)).where(
            SectionVersion.user_id == user_id,
            SectionVersion.section_id == record_id,
        )
    )
    return latest or 0


def _latest_local(db: Session, user_id: UUID, record_id: UUID) -> SectionVersion | None:
    return db.scalars(
        select(SectionVersion)
        .where(
            SectionVersion.user_id == user_id,
            SectionVersion.section_id == record_id,
        )
        .order_by(SectionVersion.version.desc())
        .limit(1)
    ).first()


def _record_conflict(
    db: Session,
    user_id: UUID,
    record_id: UUID,
    record_type: SectionType,
    local: SectionVersion | None,
    cloud_version: int,
    cloud_snapshot: dict[str, Any],
) -> None:
    """Put a disagreement in front of a person, replacing any earlier one.

    Replacing rather than accumulating: a record has one current state on each
    side, so a second conflict about it is the same question with fresher
    answers, not another question.
    """
    existing = db.scalar(
        select(SyncConflict).where(
            SyncConflict.user_id == user_id, SyncConflict.record_id == record_id
        )
    )

    values = {
        "record_type": record_type,
        "local_version": 0 if local is None else local.version,
        "cloud_version": cloud_version,
        "local_snapshot": {} if local is None else local.snapshot,
        "cloud_snapshot": cloud_snapshot,
    }

    if existing is None:
        db.add(SyncConflict(user_id=user_id, record_id=record_id, **values))
        return

    for name, value in values.items():
        setattr(existing, name, value)


def pull_once(
    db: Session, state: SyncState, cloud: Cloud, report: SyncReport, limit: int = 500
) -> bool:
    """Apply one page of the account's changes. Returns whether more remain."""
    known = _agreements(db, state.user_id)
    feed = cloud.pull(state.cloud_cursor, limit)

    for change in feed["changes"]:
        record_id = UUID(str(change["record_id"]))
        record_type = SectionType(change["record_type"])
        operation = OperationType(change["operation"])
        agreement = known.get(record_id)

        # Our own writes come back to us: what this database pushed a moment
        # ago is now part of the account's history too. Applying it again would
        # make new local history, which the next push would offer back, which
        # the pull after that would return — a library that never settles.
        if agreement is not None and change["version"] <= agreement.cloud_version:
            continue

        here = _local_version(db, state.user_id, record_id)
        changed_here = here > (0 if agreement is None else agreement.local_version)

        if changed_here:
            # both sides moved since they last agreed
            _record_conflict(
                db,
                state.user_id,
                record_id,
                record_type,
                _latest_local(db, state.user_id, record_id),
                change["version"],
                change["snapshot"],
            )
            report.conflicts.append(record_id)
            continue

        try:
            if operation is OperationType.DELETE:
                apply_delete(db, state.user_id, record_type, record_id)
            else:
                apply_snapshot(
                    db, state.user_id, record_type, record_id, change["snapshot"]
                )
        except UnapplicableChange as error:
            report.rejected.append(f"{record_type.value} {record_id}: {error}")
            continue

        # the account's change becomes this database's own history too, so a
        # later sync can tell it apart from something edited here
        entry = stage_version(
            db,
            state.user_id,
            record_type,
            record_id,
            operation,
            change["snapshot"],
        )
        db.flush()

        _agree(
            db,
            state.user_id,
            record_id,
            record_type,
            entry.version,
            change["version"],
            known,
        )
        report.pulled += 1

    state.cloud_cursor = feed["cursor"]
    db.commit()

    return bool(feed["more"])


def push_once(
    db: Session, state: SyncState, cloud: Cloud, report: SyncReport, limit: int = 500
) -> bool:
    """Offer one page of this database's changes. Returns whether more remain."""
    known = _agreements(db, state.user_id)

    rows = db.scalars(
        select(SectionVersion)
        .where(
            SectionVersion.user_id == state.user_id,
            SectionVersion.seq > state.local_cursor,
        )
        .order_by(SectionVersion.seq)
        .limit(limit + 1)
    ).all()

    more = len(rows) > limit
    page = list(rows[:limit])
    if not page:
        return False

    # A record edited several times offline is offered once, as it now stands.
    # Replaying every keystroke would be a conflict per intermediate version
    # against a server that only ever had the last one.
    latest_by_record: dict[UUID, SectionVersion] = {}
    for row in page:
        latest_by_record[row.section_id] = row

    conflicted = {
        row.record_id
        for row in db.scalars(
            select(SyncConflict).where(SyncConflict.user_id == state.user_id)
        ).all()
    }

    def already_agreed(row: SectionVersion) -> bool:
        """Whether this is a change the account gave us, not one we made.

        The other half of the loop above: a pulled change is recorded in this
        database's history too, and would otherwise be offered straight back to
        the account it came from.
        """
        agreement = known.get(row.section_id)
        return agreement is not None and row.version <= agreement.local_version

    offered = [
        row
        for row in latest_by_record.values()
        if row.section_id not in conflicted and not already_agreed(row)
    ]

    if offered:
        response = cloud.push(
            [
                {
                    "record_type": row.section_type.value,
                    "record_id": str(row.section_id),
                    "base_version": (
                        known[row.section_id].cloud_version
                        if row.section_id in known
                        else None
                    ),
                    "operation": row.operation.value,
                    "snapshot": row.snapshot,
                }
                for row in offered
            ]
        )

        by_id = {row.section_id: row for row in offered}
        for result in response["results"]:
            record_id = UUID(str(result["record_id"]))
            row = by_id[record_id]

            if result["outcome"] == "applied":
                _agree(
                    db,
                    state.user_id,
                    record_id,
                    row.section_type,
                    row.version,
                    result["version"],
                    known,
                )
                report.pushed += 1
            elif result["outcome"] == "conflict":
                theirs = result.get("theirs") or {}
                _record_conflict(
                    db,
                    state.user_id,
                    record_id,
                    row.section_type,
                    row,
                    result.get("version") or 0,
                    theirs.get("snapshot", {}),
                )
                report.conflicts.append(record_id)
            else:
                report.rejected.append(
                    f"{row.section_type.value} {record_id}: {result.get('reason')}"
                )

    # The cursor advances past everything offered, conflicts included. A
    # conflict is remembered as itself and re-offered only once resolved;
    # leaving the cursor behind would mean re-reading the same history on every
    # run for as long as it went unanswered.
    state.local_cursor = page[-1].seq
    db.commit()

    return more


def sync(db: Session, state: SyncState, cloud: Cloud, limit: int = 500) -> SyncReport:
    """Bring this database and the account level with each other."""
    report = SyncReport()

    while pull_once(db, state, cloud, report, limit):
        pass

    while push_once(db, state, cloud, report, limit):
        pass

    return report


class Resolution(str, Enum):
    """Which side of a disagreement a person chose."""

    MINE = "mine"
    THEIRS = "theirs"


def resolve_conflict(
    db: Session, user_id: UUID, record_id: UUID, choice: Resolution
) -> None:
    """Answer a conflict, so the next sync can carry the answer out.

    Neither choice writes to the account directly. Keeping mine records that
    this database has now seen the account's version — so the next push offers
    ours against a version the account still holds, and it applies rather than
    conflicting again. Keeping theirs applies their snapshot here and agrees on
    it, which leaves nothing to push.

    Either way the sync that follows does the work, so being interrupted leaves
    the choice recorded rather than half carried out.
    """
    conflict = db.scalar(
        select(SyncConflict).where(
            SyncConflict.user_id == user_id, SyncConflict.record_id == record_id
        )
    )
    if conflict is None:
        raise LookupError(f"no conflict for {record_id}")

    known = _agreements(db, user_id)

    if choice is Resolution.THEIRS:
        try:
            apply_snapshot(
                db, user_id, conflict.record_type, record_id, conflict.cloud_snapshot
            )
        except UnapplicableChange:
            db.rollback()
            raise

        entry = stage_version(
            db,
            user_id,
            conflict.record_type,
            record_id,
            OperationType.UPDATE,
            conflict.cloud_snapshot,
        )
        db.flush()
        _agree(
            db,
            user_id,
            record_id,
            conflict.record_type,
            entry.version,
            conflict.cloud_version,
            known,
        )
    else:
        # Ours stands, but saying so has to be a change of its own. The edit
        # that caused the conflict is already behind the push cursor — the sync
        # that found the conflict read past it — so without a new entry there
        # would be nothing left to offer and the choice would never leave this
        # machine.
        #
        # Agreeing to the account's version number without taking its content
        # is the other half: the next push offers ours against the version the
        # account actually holds, so it applies instead of colliding again.
        stage_version(
            db,
            user_id,
            conflict.record_type,
            record_id,
            OperationType.UPDATE,
            conflict.local_snapshot,
        )
        _agree(
            db,
            user_id,
            record_id,
            conflict.record_type,
            0,
            conflict.cloud_version,
            known,
        )

    db.delete(conflict)
    db.commit()

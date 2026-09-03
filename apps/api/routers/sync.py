"""Reconciling a desktop library with an account.

The desktop works whether or not anyone is signed in, so the two copies drift
by design: someone edits on a plane, and the account knows nothing about it
until they land. Reconciling them is reading each side's history and deciding,
per record, whether one side's change can simply be applied or whether both
sides changed and a person has to say which they meant.

This is the reading half. A client stores the sequence number it last applied
and asks for what came after; the history is already ordered, already carries
what each record looked like, and already outlives deletes, so there is nothing
to reconstruct here.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from deps.auth import CurrentUser
from deps.db import Db
from enums import OperationType
from models.section_version import SectionVersion
from schemas.sync import (
    Change,
    ChangeFeed,
    PullQuery,
    PushChange,
    PushOutcome,
    PushRequest,
    PushResponse,
    PushResult,
)
from services.record_section import MAX_ATTEMPTS, stage_version
from services.sync_apply import UnapplicableChange, apply_delete, apply_snapshot

router = APIRouter(prefix="/sync", tags=["Sync"])

#: The paging arguments, read from the query string. Annotated rather than a
#: default so it matches CurrentUser and Db, the other dependencies here.
Paging = Annotated[PullQuery, Depends()]


@router.get("/changes", response_model=ChangeFeed, status_code=status.HTTP_200_OK)
def pull_changes(
    current_user: CurrentUser,
    db: Db,
    query: Paging,
) -> ChangeFeed:
    """Everything that has happened to this account's records since ``since``.

    Paged rather than complete, because a library that has been edited for
    years is not something to assemble in memory on either end. Changes are not
    collapsed to the latest state of each record: replaying an intermediate
    version costs a write the client would have made anyway, and collapsing
    within a page would mean deciding what "latest" means without having seen
    the pages after it.
    """
    # one more than asked for, so a full page can be distinguished from the end
    # of the history without a second count query
    rows = db.scalars(
        select(SectionVersion)
        .where(
            SectionVersion.user_id == current_user.id,
            SectionVersion.seq > query.since,
        )
        .order_by(SectionVersion.seq)
        .limit(query.limit + 1)
    ).all()

    more = len(rows) > query.limit
    page = rows[: query.limit]

    return ChangeFeed(
        changes=[_as_change(row) for row in page],
        # staying put when there is nothing new is what makes it safe for a
        # client to store this unconditionally
        cursor=page[-1].seq if page else query.since,
        more=more,
    )


def _as_change(row: SectionVersion) -> Change:
    return Change(
        record_type=row.section_type,
        record_id=row.section_id,
        version=row.version,
        operation=row.operation,
        snapshot=row.snapshot,
        seq=row.seq,
    )


def _latest(db: Db, user_id: UUID, record_id: UUID) -> SectionVersion | None:
    """The most recent thing this account did to a record, if anything."""
    return db.scalars(
        select(SectionVersion)
        .where(
            SectionVersion.user_id == user_id,
            SectionVersion.section_id == record_id,
        )
        .order_by(SectionVersion.version.desc())
        .limit(1)
    ).first()


def _apply_one(
    db: Db, user_id: UUID, change: PushChange, latest: SectionVersion | None
) -> PushResult:
    """Write one offered change, or say why it was not written."""
    # The record and the entry describing it are written in one transaction,
    # so a retry has to redo both. Retrying only the entry would leave the
    # history claiming a change that was rolled back with it.
    for attempt in range(MAX_ATTEMPTS):
        try:
            if change.operation is OperationType.DELETE:
                apply_delete(db, user_id, change.record_type, change.record_id)
            else:
                apply_snapshot(
                    db, user_id, change.record_type, change.record_id, change.snapshot
                )

            entry = stage_version(
                db,
                user_id,
                change.record_type,
                change.record_id,
                change.operation,
                change.snapshot,
            )
            db.commit()
        except UnapplicableChange as error:
            db.rollback()
            return PushResult(
                record_id=change.record_id,
                record_type=change.record_type,
                outcome=PushOutcome.REJECTED,
                reason=str(error),
            )
        except IntegrityError:
            # somebody else took the sequence number between reading it and
            # writing it; everything here is redone against what they left
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                raise
            continue

        return PushResult(
            record_id=change.record_id,
            record_type=change.record_type,
            outcome=PushOutcome.APPLIED,
            version=entry.version,
            seq=entry.seq,
        )

    # unreachable: the loop either returns or raises on its last attempt
    raise AssertionError("push fell out of its retry loop")


@router.post("/push", response_model=PushResponse, status_code=status.HTTP_200_OK)
def push_changes(
    current_user: CurrentUser, db: Db, payload: PushRequest
) -> PushResponse:
    """Offer changes made elsewhere, and be told what became of each.

    Each change carries the version of its record that the client last agreed
    with this server. If that is still the version here, nobody else has
    touched it and the change is applied. If it is not, both sides changed the
    same record and this says so rather than choosing — the response carries
    what the server has, which is the other half of the question a person then
    gets asked.

    Applied one at a time rather than as a single transaction, because the
    answer is per record: one conflicted resume should not send back a whole
    library that would otherwise have gone through. A client re-offers what did
    not land.
    """
    results: list[PushResult] = []

    for change in payload.changes:
        latest = _latest(db, current_user.id, change.record_id)
        server_version = None if latest is None else latest.version

        if server_version != change.base_version:
            results.append(
                PushResult(
                    record_id=change.record_id,
                    record_type=change.record_type,
                    outcome=PushOutcome.CONFLICT,
                    version=server_version,
                    theirs=None if latest is None else _as_change(latest),
                )
            )
            continue

        results.append(_apply_one(db, current_user.id, change, latest))

    return PushResponse(results=results)

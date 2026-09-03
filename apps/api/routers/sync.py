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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import get_settings
from deps.auth import CurrentUser
from deps.db import Db
from enums import OperationType
from models.section_version import SectionVersion
from models.sync_state import SyncConflict, SyncState
from schemas.sync import (
    Change,
    ChangeFeed,
    ConflictRead,
    ConnectRequest,
    PullQuery,
    PushChange,
    PushOutcome,
    PushRequest,
    PushResponse,
    PushResult,
    ResolveRequest,
    RunReport,
    SyncStatus,
)
from services.cloud_client import (
    CloudApi,
    CloudRejectedCredentials,
    CloudUnreachable,
    sign_in,
)
from services.record_section import MAX_ATTEMPTS, stage_version
from services.sync_apply import UnapplicableChange, apply_delete, apply_snapshot
from services.sync_engine import Resolution, resolve_conflict, sync

settings = get_settings()

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


# ---------------------------------------------------------------------------
# The desktop's own controls.
#
# Only a local install has two copies to reconcile: the hosted API is one of
# the two, and asking it to sync with itself is meaningless rather than merely
# unnecessary. These say so rather than quietly doing nothing.
# ---------------------------------------------------------------------------


def _local_only() -> None:
    if not settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="this API is the account; there is nothing for it to sync with",
        )


def _state(db: Db, user_id: UUID) -> SyncState | None:
    return db.scalar(select(SyncState).where(SyncState.user_id == user_id))


def _conflicts(db: Db, user_id: UUID) -> list[ConflictRead]:
    rows = db.scalars(select(SyncConflict).where(SyncConflict.user_id == user_id)).all()
    return [
        ConflictRead(
            record_id=row.record_id,
            record_type=row.record_type,
            local_version=row.local_version,
            cloud_version=row.cloud_version,
            local_snapshot=row.local_snapshot,
            cloud_snapshot=row.cloud_snapshot,
        )
        for row in rows
    ]


@router.get("/status", response_model=SyncStatus)
def sync_status(current_user: CurrentUser, db: Db) -> SyncStatus:
    """Whether this library is connected to an account, and what is outstanding."""
    _local_only()
    state = _state(db, current_user.id)

    if state is None:
        return SyncStatus(connected=False)

    return SyncStatus(
        connected=True,
        account_email=state.account_email,
        cloud_cursor=state.cloud_cursor,
        local_cursor=state.local_cursor,
        conflicts=_conflicts(db, current_user.id),
    )


@router.post("/connect", response_model=SyncStatus)
def connect_account(
    payload: ConnectRequest, current_user: CurrentUser, db: Db
) -> SyncStatus:
    """Sign this library in to an account.

    Nothing is transferred here. Connecting only records who this library
    belongs to; the first sync afterwards is what carries the work across, and
    it is the same code as every sync after it rather than a special first one.
    """
    _local_only()

    try:
        token, email = sign_in(payload.base_url, payload.email, payload.password)
    except CloudRejectedCredentials as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error
    except CloudUnreachable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    state = _state(db, current_user.id)
    if state is None:
        state = SyncState(user_id=current_user.id, account_email=email)
        db.add(state)

    state.account_email = email
    state.access_token = token
    state.cloud_base_url = payload.base_url
    db.commit()

    return sync_status(current_user, db)


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_account(current_user: CurrentUser, db: Db) -> None:
    """Forget the account. The library stays exactly as it is."""
    _local_only()

    state = _state(db, current_user.id)
    if state is not None:
        db.delete(state)
        db.commit()


@router.post("/run", response_model=RunReport)
def run_sync(current_user: CurrentUser, db: Db) -> RunReport:
    """Bring this library and the account level with each other."""
    _local_only()

    state = _state(db, current_user.id)
    if state is None or state.access_token is None or state.cloud_base_url is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="this library is not connected to an account",
        )

    try:
        with CloudApi(state.cloud_base_url, state.access_token) as cloud:
            report = sync(db, state, cloud)
    except CloudRejectedCredentials as error:
        # the session expired; the library is still connected, but somebody has
        # to sign in again
        state.access_token = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error
    except CloudUnreachable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    return RunReport(
        pulled=report.pulled,
        pushed=report.pushed,
        conflicts=report.conflicts,
        rejected=report.rejected,
    )


@router.post("/conflicts/{record_id}/resolve", response_model=SyncStatus)
def resolve(
    record_id: UUID, payload: ResolveRequest, current_user: CurrentUser, db: Db
) -> SyncStatus:
    """Say which side of a disagreement was meant.

    The choice is recorded here and carried out by the next sync, so answering
    a pile of conflicts is not a pile of network calls that can half fail.
    """
    _local_only()

    try:
        resolve_conflict(db, current_user.id, record_id, Resolution(payload.choice))
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except UnapplicableChange as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error

    return sync_status(current_user, db)

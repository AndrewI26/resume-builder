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

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from deps.auth import CurrentUser
from deps.db import Db
from models.section_version import SectionVersion
from schemas.sync import Change, ChangeFeed, PullQuery

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
        changes=[
            Change(
                record_type=row.section_type,
                record_id=row.section_id,
                version=row.version,
                operation=row.operation,
                snapshot=row.snapshot,
                seq=row.seq,
            )
            for row in page
        ],
        # staying put when there is nothing new is what makes it safe for a
        # client to store this unconditionally
        cursor=page[-1].seq if page else query.since,
        more=more,
    )

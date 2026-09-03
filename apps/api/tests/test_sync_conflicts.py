"""Answering a conflict, and what happens on the sync afterwards.

Recording a disagreement is only half of it. The half that matters to somebody
using the app is that choosing an answer ends the disagreement — and that the
sync after the choice does not simply find it again.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.education import Education
from models.sync_state import SyncConflict, SyncState
from models.user import User
from services.sync_engine import Resolution, resolve_conflict, sync
from tests.conftest import Account, local_education


@pytest.fixture
def diverged(
    auth: Any, db: Session, user: User, state: SyncState, account: Account
) -> uuid.UUID:
    """A record edited on both sides, with the conflict already recorded."""
    client = auth(user)
    created = local_education(client, "Shared")
    sync(db, state, account)
    record_id = uuid.UUID(created["id"])

    account.push(
        [
            {
                "record_type": "education",
                "record_id": str(record_id),
                "base_version": 1,
                "operation": "update",
                "snapshot": {
                    "name": "Their edit",
                    "subheading": "BSc",
                    "duration": "2016 - 2020",
                    "location": "Boston, MA",
                },
            }
        ]
    )
    client.put(
        f"/education/{record_id}",
        json={
            "name": "My edit",
            "subheading": "BSc",
            "duration": "2016 - 2020",
            "location": "Boston, MA",
        },
    )

    report = sync(db, state, account)
    assert report.conflicts == [record_id]

    return record_id


def conflicts(db: Session, user: User) -> list[SyncConflict]:
    return list(
        db.scalars(select(SyncConflict).where(SyncConflict.user_id == user.id)).all()
    )


class TestKeepingMine:
    def test_the_local_version_reaches_the_account(
        self, diverged, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        resolve_conflict(db, user.id, diverged, Resolution.MINE)

        sync(db, state, account)

        theirs = account.pull(0, 100)["changes"]
        assert theirs[-1]["snapshot"]["name"] == "My edit"

    def test_the_record_here_is_untouched(
        self, diverged, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        resolve_conflict(db, user.id, diverged, Resolution.MINE)
        sync(db, state, account)

        db.expire_all()
        stored = db.get(Education, diverged)
        assert stored is not None and stored.name == "My edit"


class TestKeepingTheirs:
    def test_the_account_s_version_replaces_the_local_one(
        self, diverged, db: Session, user: User
    ) -> None:
        resolve_conflict(db, user.id, diverged, Resolution.THEIRS)

        db.expire_all()
        stored = db.get(Education, diverged)
        assert stored is not None and stored.name == "Their edit"

    def test_the_next_sync_has_nothing_to_argue_about(
        self, diverged, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        resolve_conflict(db, user.id, diverged, Resolution.THEIRS)

        report = sync(db, state, account)

        assert report.conflicts == []
        assert conflicts(db, user) == []


class TestAfterAnswering:
    @pytest.mark.parametrize("choice", [Resolution.MINE, Resolution.THEIRS])
    def test_the_conflict_is_gone(
        self, diverged, db: Session, user: User, choice: Resolution
    ) -> None:
        resolve_conflict(db, user.id, diverged, choice)

        assert conflicts(db, user) == []

    @pytest.mark.parametrize("choice", [Resolution.MINE, Resolution.THEIRS])
    def test_it_does_not_come_back_on_the_next_sync(
        self,
        diverged,
        db: Session,
        user: User,
        state: SyncState,
        account: Account,
        choice: Resolution,
    ) -> None:
        """An answered question that keeps being re-asked is not answered."""
        resolve_conflict(db, user.id, diverged, choice)

        sync(db, state, account)
        sync(db, state, account)

        assert conflicts(db, user) == []

    @pytest.mark.parametrize("choice", [Resolution.MINE, Resolution.THEIRS])
    def test_both_sides_end_up_holding_the_same_thing(
        self,
        diverged,
        db: Session,
        user: User,
        state: SyncState,
        account: Account,
        choice: Resolution,
    ) -> None:
        """The point of the whole exercise."""
        resolve_conflict(db, user.id, diverged, choice)
        sync(db, state, account)
        sync(db, state, account)

        db.expire_all()
        here = db.get(Education, diverged)
        assert here is not None

        theirs = [
            change
            for change in account.pull(0, 100)["changes"]
            if change["record_id"] == str(diverged)
        ][-1]

        assert here.name == theirs["snapshot"]["name"]


class TestAnsweringSomethingThatIsNotThere:
    def test_it_says_so(self, db: Session, user: User) -> None:
        with pytest.raises(LookupError):
            resolve_conflict(db, user.id, uuid.uuid4(), Resolution.MINE)

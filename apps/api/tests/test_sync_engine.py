"""Two databases reconciling, which is the only way to know sync works.

The endpoints have their own tests and pass in isolation; what those cannot
show is that a desktop and an account end up holding the same thing. So this
stands up a second, entirely separate database as the account — its own engine,
its own user, reached through the real push and pull endpoints — and runs the
engine against it.

The account calls the endpoint functions directly against its own session,
rather than going through the app. The app is one object with one set of
dependency overrides, so it cannot serve two databases at once — and the HTTP
layer over these two endpoints already has its own tests. What is under test
here is whether two databases converge.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.education import Education
from models.section_version import SectionVersion
from models.sync_state import SyncAgreement, SyncConflict, SyncState
from models.user import User
from services.sync_engine import sync
from tests.conftest import Account, local_education


class TestFirstSync:
    def test_a_library_made_offline_reaches_the_account(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """Signing in for the first time with work already done."""
        client = auth(user)
        created = local_education(client, "State University")

        report = sync(db, state, account)

        assert report.pushed == 1
        assert report.conflicts == []

        # ask the account for it, rather than trusting the report
        theirs = account.pull(0, 100)["changes"]
        assert [c["record_id"] for c in theirs] == [created["id"]]
        assert theirs[0]["snapshot"]["name"] == "State University"

    def test_the_record_keeps_its_identity_across(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """The same record, not a copy that resembles it."""
        created = local_education(auth(user), "State University")
        sync(db, state, account)

        agreement = db.scalar(
            select(SyncAgreement).where(
                SyncAgreement.record_id == uuid.UUID(created["id"])
            )
        )
        assert agreement is not None
        assert agreement.cloud_version == 1

    def test_syncing_twice_changes_nothing(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """The property that makes a sync safe to run whenever."""
        local_education(auth(user), "State University")
        sync(db, state, account)

        second = sync(db, state, account)

        assert second.pushed == 0
        assert second.pulled == 0
        assert second.conflicts == []


class TestPullingFromTheAccount:
    def test_work_done_elsewhere_arrives(
        self, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """Someone edited on another machine while this one was away."""
        record_id = uuid.uuid4()
        account.push(
            [
                {
                    "record_type": "education",
                    "record_id": str(record_id),
                    "base_version": None,
                    "operation": "create",
                    "snapshot": {
                        "name": "Elsewhere College",
                        "subheading": "BSc",
                        "duration": "2016 - 2020",
                        "location": "Boston, MA",
                    },
                }
            ]
        )

        report = sync(db, state, account)

        assert report.pulled == 1
        stored = db.get(Education, record_id)
        assert stored is not None
        assert stored.name == "Elsewhere College"
        assert stored.user_id == user.id, "owned by whoever holds this database"

    def test_a_deletion_elsewhere_is_carried_out_here(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        created = local_education(auth(user), "State University")
        sync(db, state, account)
        record_id = uuid.UUID(created["id"])

        account.push(
            [
                {
                    "record_type": "education",
                    "record_id": str(record_id),
                    "base_version": 1,
                    "operation": "delete",
                    "snapshot": {},
                }
            ]
        )

        report = sync(db, state, account)

        assert report.pulled == 1
        assert db.get(Education, record_id) is None


class TestConflicts:
    def _diverge(
        self,
        auth: Any,
        db: Session,
        user: User,
        state: SyncState,
        account: Account,
    ) -> uuid.UUID:
        """Get both sides holding a different edit of the same record."""
        client = auth(user)
        created = local_education(client, "Shared")
        sync(db, state, account)
        record_id = uuid.UUID(created["id"])

        # edited on the other machine
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

        # and here, offline
        response = client.put(
            f"/education/{record_id}",
            json={
                "name": "My edit",
                "subheading": "BSc",
                "duration": "2016 - 2020",
                "location": "Boston, MA",
            },
        )
        assert response.status_code == 200, response.text

        return record_id

    def test_both_sides_editing_is_reported_rather_than_resolved(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        record_id = self._diverge(auth, db, user, state, account)

        report = sync(db, state, account)

        assert report.conflicts == [record_id]
        assert report.had_conflicts

    def test_neither_side_is_overwritten(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """The whole point of stopping: losing an edit silently is the failure."""
        record_id = self._diverge(auth, db, user, state, account)

        sync(db, state, account)

        db.expire_all()
        here = db.get(Education, record_id)
        assert here is not None and here.name == "My edit"

        theirs = account.pull(0, 100)["changes"][-1]
        assert theirs["snapshot"]["name"] == "Their edit"

    def test_the_conflict_keeps_both_answers_for_the_prompt(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        record_id = self._diverge(auth, db, user, state, account)

        sync(db, state, account)

        conflict = db.scalar(
            select(SyncConflict).where(SyncConflict.record_id == record_id)
        )
        assert conflict is not None
        assert conflict.local_snapshot["name"] == "My edit"
        assert conflict.cloud_snapshot["name"] == "Their edit"

    def test_a_conflicted_record_is_not_offered_again_every_run(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """An unanswered question should not re-ask itself forever."""
        self._diverge(auth, db, user, state, account)
        sync(db, state, account)

        second = sync(db, state, account)

        assert second.pushed == 0
        assert second.pulled == 0

    def test_other_records_still_sync_while_one_is_conflicted(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """One disagreement must not stop the rest of a library moving."""
        self._diverge(auth, db, user, state, account)
        unrelated = local_education(auth(user), "Unrelated")

        sync(db, state, account)

        theirs = account.pull(0, 100)["changes"]
        assert unrelated["id"] in {c["record_id"] for c in theirs}


class TestOfflineEditing:
    def test_several_edits_offline_arrive_as_the_current_state(
        self, auth, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """Replaying every keystroke would conflict against its own history."""
        client = auth(user)
        created = local_education(client, "First")
        record_id = created["id"]

        for name in ("Second", "Third"):
            client.put(
                f"/education/{record_id}",
                json={
                    "name": name,
                    "subheading": "BSc",
                    "duration": "2016 - 2020",
                    "location": "Boston, MA",
                },
            )

        report = sync(db, state, account)

        assert report.conflicts == []
        theirs = account.pull(0, 100)["changes"]
        assert [c["snapshot"]["name"] for c in theirs] == ["Third"]

    def test_the_local_history_records_what_arrived(
        self, db: Session, user: User, state: SyncState, account: Account
    ) -> None:
        """A pulled change is a change here too, or the next sync re-offers it."""
        account.push(
            [
                {
                    "record_type": "education",
                    "record_id": str(uuid.uuid4()),
                    "base_version": None,
                    "operation": "create",
                    "snapshot": {
                        "name": "Elsewhere",
                        "subheading": "BSc",
                        "duration": "2016 - 2020",
                        "location": "Boston, MA",
                    },
                }
            ]
        )

        sync(db, state, account)

        entries = db.scalars(
            select(SectionVersion).where(SectionVersion.user_id == user.id)
        ).all()
        assert len(entries) == 1

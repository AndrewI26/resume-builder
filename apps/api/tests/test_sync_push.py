"""Offering changes made somewhere else.

The interesting cases are the ones where the two sides disagree, and the one
where a caller names a record that was never theirs — which is the only way
this endpoint could be worse than the rest of the API, since every other one
finds its rows by owner and this one is handed an id.
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.education import Education
from models.expirence import Expirence
from models.section_version import SectionVersion
from models.user import User
from services.bullet_points import bullet_points_by_id
from services.record_section import stage_version

# the wire shape, which is JSON rather than any of the app's own types
Change = dict[str, Any]


def education_change(
    record_id: uuid.UUID, name: str, base: int | None = None
) -> Change:
    return {
        "record_type": "education",
        "record_id": str(record_id),
        "base_version": base,
        "operation": "create" if base is None else "update",
        "snapshot": {
            "name": name,
            "subheading": "BSc",
            "duration": "2016 - 2020",
            "location": "Boston, MA",
        },
    }


def push(client: TestClient, *changes: Change) -> list[Change]:
    response = client.post("/sync/push", json={"changes": list(changes)})
    assert response.status_code == 200, response.text
    results: list[Change] = response.json()["results"]
    return results


class TestApplying:
    def test_a_record_made_offline_arrives_keeping_its_id(
        self, auth, db: Session, user: User
    ) -> None:
        """The same record on both sides, rather than two that resemble each other."""
        record_id = uuid.uuid4()

        (result,) = push(auth(user), education_change(record_id, "State University"))

        assert result["outcome"] == "applied"
        assert result["version"] == 1

        stored = db.get(Education, record_id)
        assert stored is not None
        assert stored.name == "State University"
        assert stored.user_id == user.id

    def test_applying_again_updates_rather_than_duplicates(
        self, auth, db: Session, user: User
    ) -> None:
        client = auth(user)
        record_id = uuid.uuid4()
        push(client, education_change(record_id, "State University"))

        (result,) = push(client, education_change(record_id, "Renamed", base=1))

        assert result["outcome"] == "applied"
        assert result["version"] == 2
        stored = db.get(Education, record_id)
        assert stored is not None and stored.name == "Renamed"

    def test_it_reports_where_the_change_landed_in_the_history(
        self, auth, user: User
    ) -> None:
        """So a client can skip its own writes instead of pulling them back."""
        (result,) = push(auth(user), education_change(uuid.uuid4(), "State"))

        assert result["seq"] == 1

    def test_a_delete_removes_the_record(self, auth, db: Session, user: User) -> None:
        client = auth(user)
        record_id = uuid.uuid4()
        push(client, education_change(record_id, "State University"))

        (result,) = push(
            client,
            {
                "record_type": "education",
                "record_id": str(record_id),
                "base_version": 1,
                "operation": "delete",
                "snapshot": {},
            },
        )

        assert result["outcome"] == "applied"
        assert db.get(Education, record_id) is None

    def test_deleting_something_already_gone_is_not_a_failure(
        self, auth, user: User
    ) -> None:
        """Both sides deciding to delete the same thing agreed with each other."""
        (result,) = push(
            auth(user),
            {
                "record_type": "education",
                "record_id": str(uuid.uuid4()),
                "base_version": None,
                "operation": "delete",
                "snapshot": {},
            },
        )

        assert result["outcome"] == "applied"


class TestConflicts:
    def test_an_edit_against_a_stale_version_conflicts(
        self, auth, db: Session, user: User
    ) -> None:
        """Somebody changed it here while the other side was away."""
        client = auth(user)
        record_id = uuid.uuid4()
        push(client, education_change(record_id, "State University"))
        push(client, education_change(record_id, "Edited here", base=1))

        # the offline side still believes it is at version 1
        (result,) = push(client, education_change(record_id, "Edited there", base=1))

        assert result["outcome"] == "conflict"
        assert result["version"] == 2

        stored = db.get(Education, record_id)
        assert stored is not None
        assert stored.name == "Edited here", "a conflict must not overwrite"

    def test_a_conflict_carries_what_the_server_has(self, auth, user: User) -> None:
        """The other half of the question a person is asked."""
        client = auth(user)
        record_id = uuid.uuid4()
        push(client, education_change(record_id, "State University"))
        push(client, education_change(record_id, "Edited here", base=1))

        (result,) = push(client, education_change(record_id, "Edited there", base=1))

        assert result["theirs"]["snapshot"]["name"] == "Edited here"
        assert result["theirs"]["version"] == 2

    def test_claiming_a_record_is_new_when_it_is_not_conflicts(
        self, auth, user: User
    ) -> None:
        """Two sides can create the same id only by one of them being wrong."""
        client = auth(user)
        record_id = uuid.uuid4()
        push(client, education_change(record_id, "State University"))

        (result,) = push(client, education_change(record_id, "Also mine"))

        assert result["outcome"] == "conflict"

    def test_one_conflict_does_not_hold_up_the_rest(
        self, auth, db: Session, user: User
    ) -> None:
        """A whole library should not bounce because one record disagrees."""
        client = auth(user)
        contested, fine = uuid.uuid4(), uuid.uuid4()
        push(client, education_change(contested, "First"))
        push(client, education_change(contested, "Moved on", base=1))

        results = push(
            client,
            education_change(contested, "Stale", base=1),
            education_change(fine, "Brand new"),
        )

        assert [r["outcome"] for r in results] == ["conflict", "applied"]
        assert db.get(Education, fine) is not None


class TestOwnership:
    def test_it_will_not_write_over_someone_else_s_record(
        self, auth, db: Session, user: User, other_user: User, make_education
    ) -> None:
        """The one way this endpoint could be worse than the rest of the API.

        Every other endpoint finds rows by owner. This one is handed an id, and
        the caller's own history says nothing about a record that was never
        theirs — so without an explicit check the version test would see a new
        record and wave it through.
        """
        theirs = make_education(other_user, name="Their University")

        (result,) = push(auth(user), education_change(theirs.id, "Stolen"))

        assert result["outcome"] == "rejected"
        assert "someone else" in result["reason"]

        db.expire_all()
        stored = db.get(Education, theirs.id)
        assert stored is not None
        assert stored.name == "Their University"
        assert stored.user_id == other_user.id

    def test_it_needs_a_session(self, client: TestClient) -> None:
        response = client.post("/sync/push", json={"changes": []})

        assert response.status_code == 401


class TestRecordsWithBulletPoints:
    def test_an_experience_arrives_with_its_bullets(
        self, auth, db: Session, user: User
    ) -> None:
        """Bullets are rows of their own, so applying one has to rebuild them."""
        record_id = uuid.uuid4()

        (result,) = push(
            auth(user),
            {
                "record_type": "experience",
                "record_id": str(record_id),
                "base_version": None,
                "operation": "create",
                "snapshot": {
                    "company": "Acme",
                    "position": "Engineer",
                    "duration": "2020 - 2022",
                    "location": "New York, NY",
                    "bullet_points": [
                        {"text": "Shipped the thing", "bolded": [[0, 6]]},
                        {"text": "And another", "bolded": []},
                    ],
                },
            },
        )

        assert result["outcome"] == "applied"

        stored = db.get(Expirence, record_id)
        assert stored is not None
        bullets = bullet_points_by_id(db, stored.bullet_points)
        assert [bullets[i].text for i in stored.bullet_points] == [
            "Shipped the thing",
            "And another",
        ]
        assert bullets[stored.bullet_points[0]].bolded == [(0, 6)]

    def test_editing_one_replaces_its_bullets(
        self, auth, db: Session, user: User
    ) -> None:
        client = auth(user)
        record_id = uuid.uuid4()

        def change(texts: list[str], base: int | None) -> Change:
            return {
                "record_type": "experience",
                "record_id": str(record_id),
                "base_version": base,
                "operation": "create" if base is None else "update",
                "snapshot": {
                    "company": "Acme",
                    "position": "Engineer",
                    "duration": "2020 - 2022",
                    "location": "New York, NY",
                    "bullet_points": [{"text": t, "bolded": []} for t in texts],
                },
            }

        push(client, change(["First", "Second"], None))
        push(client, change(["Only one now"], 1))

        db.expire_all()
        stored = db.get(Expirence, record_id)
        assert stored is not None
        bullets = bullet_points_by_id(db, stored.bullet_points)
        assert [bullets[i].text for i in stored.bullet_points] == ["Only one now"]


class TestBadInput:
    def test_a_snapshot_of_the_wrong_shape_is_refused(self, auth, user: User) -> None:
        (result,) = push(
            auth(user),
            {
                "record_type": "education",
                "record_id": str(uuid.uuid4()),
                "base_version": None,
                "operation": "create",
                "snapshot": {"nothing": "useful"},
            },
        )

        assert result["outcome"] == "rejected"

    def test_a_refusal_does_not_stop_the_others(self, auth, user: User) -> None:
        results = push(
            auth(user),
            {
                "record_type": "education",
                "record_id": str(uuid.uuid4()),
                "base_version": None,
                "operation": "create",
                "snapshot": {},
            },
            education_change(uuid.uuid4(), "Fine"),
        )

        assert [r["outcome"] for r in results] == ["rejected", "applied"]


class TestRoundTrip:
    def test_what_was_pushed_comes_back_from_pull(self, auth, user: User) -> None:
        """The two halves have to describe the same history."""
        client = auth(user)
        record_id = uuid.uuid4()
        push(client, education_change(record_id, "State University"))

        body = client.get("/sync/changes").json()

        assert [c["record_id"] for c in body["changes"]] == [str(record_id)]
        assert body["changes"][0]["record_type"] == SectionType.EDUCATION.value
        assert body["changes"][0]["operation"] == OperationType.CREATE.value


class TestTheRecordAndItsHistoryAgree:
    def test_a_retried_write_still_writes_the_record(
        self, auth, db: Session, user: User, monkeypatch
    ) -> None:
        """The history must never claim a change the data did not get.

        The sequence number is read and then written, so a second writer can
        take it in between. Recovering by retrying only the history entry would
        commit a version of a record whose row was rolled back with the first
        attempt — a library that says it changed and did not.
        """
        real = stage_version
        attempts = {"n": 0}

        def collide_once(*args: object, **kwargs: object):
            attempts["n"] += 1
            entry = real(*args, **kwargs)  # type: ignore[arg-type]
            if attempts["n"] == 1:
                # take the number this attempt just chose, from underneath it
                db.add(
                    SectionVersion(
                        user_id=user.id,
                        section_type=SectionType.SKILL,
                        section_id=uuid.uuid4(),
                        version=1,
                        seq=entry.seq,
                        operation=OperationType.CREATE,
                        snapshot={},
                    )
                )
            return entry

        # the name the router looks up, not the one it was defined under
        monkeypatch.setattr("routers.sync.stage_version", collide_once)

        record_id = uuid.uuid4()
        (result,) = push(auth(user), education_change(record_id, "State University"))

        assert attempts["n"] == 2, "the collision should have forced a retry"
        assert result["outcome"] == "applied"

        db.expire_all()
        stored = db.get(Education, record_id)
        assert stored is not None, "the row must exist, not just its history entry"
        assert stored.name == "State University"

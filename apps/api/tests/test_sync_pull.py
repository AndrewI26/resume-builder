"""Reading the history as a client that has been away.

The failure that matters here is silent: a client that stops early, or that
stores a cursor past changes it never applied, believes it is up to date while
missing work. So the paging and the cursor are pinned down directly.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.user import User
from services.record_section import record_version


def record(db: Session, user: User, title: str = "a") -> None:
    record_version(
        db,
        user.id,
        SectionType.SKILL,
        uuid.uuid4(),
        OperationType.CREATE,
        {"name": title},
    )


class TestPulling:
    def test_a_new_client_is_given_everything(
        self, auth, db: Session, user: User
    ) -> None:
        for _ in range(3):
            record(db, user)

        body = auth(user).get("/sync/changes").json()

        assert [change["seq"] for change in body["changes"]] == [1, 2, 3]
        assert body["cursor"] == 3
        assert body["more"] is False

    def test_it_only_returns_what_came_after_the_cursor(
        self, auth, db: Session, user: User
    ) -> None:
        for _ in range(3):
            record(db, user)

        body = auth(user).get("/sync/changes", params={"since": 2}).json()

        assert [change["seq"] for change in body["changes"]] == [3]
        assert body["cursor"] == 3

    def test_nothing_new_leaves_the_cursor_where_it_was(
        self, auth, db: Session, user: User
    ) -> None:
        """A client storing this unconditionally must not go backwards."""
        for _ in range(2):
            record(db, user)

        body = auth(user).get("/sync/changes", params={"since": 2}).json()

        assert body["changes"] == []
        assert body["cursor"] == 2
        assert body["more"] is False

    def test_an_empty_history_is_not_an_error(self, auth, user: User) -> None:
        """The first sync after signing up."""
        body = auth(user).get("/sync/changes").json()

        assert body == {"changes": [], "cursor": 0, "more": False}


class TestPaging:
    def test_a_page_says_when_there_is_more(
        self, auth, db: Session, user: User
    ) -> None:
        for _ in range(5):
            record(db, user)

        body = auth(user).get("/sync/changes", params={"limit": 2}).json()

        assert [change["seq"] for change in body["changes"]] == [1, 2]
        assert body["cursor"] == 2
        assert body["more"] is True

    def test_a_page_that_exactly_empties_the_history_says_so(
        self, auth, db: Session, user: User
    ) -> None:
        """The case a naive 'a full page means more' check gets wrong."""
        for _ in range(2):
            record(db, user)

        body = auth(user).get("/sync/changes", params={"limit": 2}).json()

        assert len(body["changes"]) == 2
        assert body["more"] is False

    def test_following_the_cursor_reaches_everything_exactly_once(
        self, auth, db: Session, user: User
    ) -> None:
        """What a client actually does, and the property it depends on."""
        for _ in range(7):
            record(db, user)

        client = auth(user)
        seen: list[int] = []
        cursor = 0
        while True:
            body = client.get(
                "/sync/changes", params={"since": cursor, "limit": 3}
            ).json()
            seen.extend(change["seq"] for change in body["changes"])
            cursor = body["cursor"]
            if not body["more"]:
                break

        assert seen == [1, 2, 3, 4, 5, 6, 7]


class TestOwnership:
    def test_it_is_only_ever_the_caller_s_own_history(
        self, auth, db: Session, user: User, other_user: User
    ) -> None:
        record(db, other_user, "theirs")
        record(db, user, "mine")

        body = auth(user).get("/sync/changes").json()

        assert [change["snapshot"]["name"] for change in body["changes"]] == ["mine"]

    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/sync/changes").status_code == 401


class TestWhatAChangeCarries:
    def test_a_delete_still_carries_what_was_deleted(
        self, auth, db: Session, user: User
    ) -> None:
        """There is no row left to read, so the history has to be enough."""
        section_id = uuid.uuid4()
        record_version(
            db,
            user.id,
            SectionType.EDUCATION,
            section_id,
            OperationType.DELETE,
            {"name": "State University"},
        )

        change = auth(user).get("/sync/changes").json()["changes"][0]

        assert change["operation"] == "delete"
        assert change["record_id"] == str(section_id)
        assert change["snapshot"]["name"] == "State University"

    def test_resumes_travel_alongside_sections(
        self, auth, db: Session, user: User
    ) -> None:
        record_version(
            db, user.id, SectionType.RESUME, uuid.uuid4(), OperationType.CREATE, {}
        )
        record(db, user)

        body = auth(user).get("/sync/changes").json()

        assert [change["record_type"] for change in body["changes"]] == [
            "resume",
            "skill",
        ]

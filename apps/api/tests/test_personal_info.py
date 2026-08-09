from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.personal_info import PersonalInfo

FIELDS = ("email", "phone_number", "address", "github", "linkedin", "portfolio")


def payload(**overrides):
    body = {
        "email": "me@example.com",
        "phone_number": "+1 555 0100",
        "address": "Boston, MA",
        "github": "https://github.com/example",
        "linkedin": "https://linkedin.com/in/example",
        "portfolio": "https://example.com",
    }
    body.update(overrides)
    return body


def row_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(PersonalInfo)) or 0


def get_personal_info(db: Session, personal_info_id: UUID) -> PersonalInfo | None:
    db.expire_all()
    return db.get(PersonalInfo, personal_info_id)


class TestAuthentication:
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("GET", "/personal-info/", None),
            ("POST", "/personal-info/", payload()),
            ("GET", f"/personal-info/{uuid4()}", None),
            ("PUT", f"/personal-info/{uuid4()}", {"email": "me@example.com"}),
            ("DELETE", f"/personal-info/{uuid4()}", None),
        ],
    )
    def test_requires_a_session_cookie(self, client: TestClient, method, path, body):
        response = client.request(method, path, json=body)

        assert response.status_code == 401


class TestGet:
    def test_returns_an_empty_list_for_a_new_user(self, auth, user):
        response = auth(user).get("/personal-info/")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_every_field(self, auth, user, make_personal_info):
        make_personal_info(user)

        [row] = auth(user).get("/personal-info/").json()

        assert row["email"] == "me@example.com"
        assert row["phone_number"] == "+1 555 0100"
        assert row["address"] == "Boston, MA"
        assert row["github"] == "https://github.com/example"
        assert row["linkedin"] == "https://linkedin.com/in/example"
        assert row["portfolio"] == "https://example.com"

    def test_returns_all_of_the_callers_rows(self, auth, user, make_personal_info):
        make_personal_info(user, email="first@example.com")
        make_personal_info(user, email="second@example.com")

        response = auth(user).get("/personal-info/")

        assert {row["email"] for row in response.json()} == {
            "first@example.com",
            "second@example.com",
        }

    def test_returns_only_the_callers_rows(
        self, auth, user, other_user, make_personal_info
    ):
        mine = make_personal_info(user, email="mine@example.com")
        make_personal_info(other_user, email="theirs@example.com")

        response = auth(user).get("/personal-info/")

        assert [row["id"] for row in response.json()] == [str(mine.id)]

    def test_returns_nulls_for_unset_fields(self, auth, user, make_personal_info):
        make_personal_info(user, phone_number=None, address=None)

        [row] = auth(user).get("/personal-info/").json()

        assert row["phone_number"] is None
        assert row["address"] is None
        assert row["email"] == "me@example.com"


class TestGetOne:
    def test_returns_the_personal_info(self, auth, user, make_personal_info):
        personal_info = make_personal_info(user)

        response = auth(user).get(f"/personal-info/{personal_info.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(personal_info.id)
        for field, value in payload().items():
            assert body[field] == value

    def test_returns_the_addressed_row(self, auth, user, make_personal_info):
        make_personal_info(user, email="first@example.com")
        wanted = make_personal_info(user, email="second@example.com")

        response = auth(user).get(f"/personal-info/{wanted.id}")

        assert response.json()["email"] == "second@example.com"

    def test_requires_a_session_cookie(self, client, make_personal_info, user):
        personal_info = make_personal_info(user)

        assert client.get(f"/personal-info/{personal_info.id}").status_code == 401

    def test_returns_404_for_an_unknown_id(self, auth, user):
        assert auth(user).get(f"/personal-info/{uuid4()}").status_code == 404

    def test_cannot_read_another_users_personal_info(
        self, auth, user, other_user, make_personal_info
    ):
        personal_info = make_personal_info(other_user)

        assert auth(user).get(f"/personal-info/{personal_info.id}").status_code == 404

    def test_rejects_a_malformed_id(self, auth, user):
        assert auth(user).get("/personal-info/not-a-uuid").status_code == 422


class TestCreate:
    def test_creates_personal_info(self, auth, user, db):
        response = auth(user).post("/personal-info/", json=payload())

        assert response.status_code == 201
        body = response.json()
        for field, value in payload().items():
            assert body[field] == value

        created = get_personal_info(db, UUID(body["id"]))
        assert created is not None
        assert created.user_id == user.id

    def test_every_field_is_optional(self, auth, user):
        response = auth(user).post("/personal-info/", json={})

        assert response.status_code == 201
        for field in FIELDS:
            assert response.json()[field] is None

    def test_accepts_a_partial_payload(self, auth, user):
        response = auth(user).post("/personal-info/", json={"email": "me@example.com"})

        assert response.status_code == 201
        assert response.json()["email"] == "me@example.com"
        assert response.json()["github"] is None

    def test_a_user_can_have_several(self, auth, user, db):
        before = row_count(db)

        client = auth(user)
        first = client.post("/personal-info/", json=payload(email="first@example.com"))
        second = client.post(
            "/personal-info/", json=payload(email="second@example.com")
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]
        assert row_count(db) == before + 2

    @pytest.mark.parametrize(
        ("field", "length"),
        [
            ("email", 256),
            ("phone_number", 51),
            ("address", 256),
            ("github", 2049),
            ("linkedin", 2049),
            ("portfolio", 2049),
        ],
    )
    def test_rejects_overlong_fields(self, auth, user, db, field, length):
        before = row_count(db)

        response = auth(user).post(
            "/personal-info/", json=payload(**{field: "a" * length})
        )

        assert response.status_code == 422
        assert row_count(db) == before


class TestEdit:
    def test_updates_only_the_supplied_fields(self, auth, user, make_personal_info, db):
        personal_info = make_personal_info(user, email="old@example.com")

        response = auth(user).put(
            f"/personal-info/{personal_info.id}", json={"email": "new@example.com"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "new@example.com"
        assert body["address"] == "Boston, MA"

        updated = get_personal_info(db, personal_info.id)
        assert updated is not None
        assert updated.email == "new@example.com"
        assert updated.address == "Boston, MA"

    def test_edits_only_the_addressed_row(self, auth, user, make_personal_info, db):
        target = make_personal_info(user, email="target@example.com")
        bystander = make_personal_info(user, email="bystander@example.com")

        auth(user).put(
            f"/personal-info/{target.id}", json={"email": "changed@example.com"}
        )

        untouched = get_personal_info(db, bystander.id)
        assert untouched is not None
        assert untouched.email == "bystander@example.com"

    @pytest.mark.parametrize("field", FIELDS)
    def test_a_null_clears_a_field(self, auth, user, make_personal_info, db, field):
        # These columns are nullable, so null is a real value here: it means
        # "remove this", unlike on the resume tables where it is rejected.
        personal_info = make_personal_info(user)

        response = auth(user).put(
            f"/personal-info/{personal_info.id}", json={field: None}
        )

        assert response.status_code == 200
        assert response.json()[field] is None

        updated = get_personal_info(db, personal_info.id)
        assert updated is not None
        assert getattr(updated, field) is None

    def test_clearing_one_field_leaves_the_others(self, auth, user, make_personal_info):
        personal_info = make_personal_info(user)

        response = auth(user).put(
            f"/personal-info/{personal_info.id}", json={"phone_number": None}
        )

        assert response.json()["phone_number"] is None
        assert response.json()["email"] == "me@example.com"

    def test_updates_every_field_at_once(self, auth, user, make_personal_info):
        personal_info = make_personal_info(user)
        changes = payload(
            email="other@example.com",
            phone_number="+44 20 7946 0000",
            address="London, UK",
            github="https://github.com/other",
            linkedin="https://linkedin.com/in/other",
            portfolio="https://other.example.com",
        )

        response = auth(user).put(f"/personal-info/{personal_info.id}", json=changes)

        assert response.status_code == 200
        for field, value in changes.items():
            assert response.json()[field] == value

    def test_rejects_an_update_with_no_fields(self, auth, user, make_personal_info):
        personal_info = make_personal_info(user)

        response = auth(user).put(f"/personal-info/{personal_info.id}", json={})

        assert response.status_code == 400

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).put(
            f"/personal-info/{uuid4()}", json={"email": "ghost@example.com"}
        )

        assert response.status_code == 404

    def test_cannot_edit_another_users_personal_info(
        self, auth, user, other_user, make_personal_info, db
    ):
        theirs = make_personal_info(other_user, email="theirs@example.com")

        response = auth(user).put(
            f"/personal-info/{theirs.id}", json={"email": "hijacked@example.com"}
        )

        assert response.status_code == 404

        untouched = get_personal_info(db, theirs.id)
        assert untouched is not None
        assert untouched.email == "theirs@example.com"


class TestDelete:
    def test_deletes_the_personal_info(self, auth, user, make_personal_info, db):
        personal_info = make_personal_info(user)

        response = auth(user).delete(f"/personal-info/{personal_info.id}")

        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"
        assert get_personal_info(db, personal_info.id) is None

    def test_leaves_other_rows_alone(self, auth, user, make_personal_info, db):
        doomed = make_personal_info(user, email="doomed@example.com")
        survivor = make_personal_info(user, email="survivor@example.com")

        auth(user).delete(f"/personal-info/{doomed.id}")

        assert get_personal_info(db, survivor.id) is not None

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).delete(f"/personal-info/{uuid4()}")

        assert response.status_code == 404

    def test_cannot_delete_another_users_personal_info(
        self, auth, user, other_user, make_personal_info, db
    ):
        theirs = make_personal_info(other_user)

        response = auth(user).delete(f"/personal-info/{theirs.id}")

        assert response.status_code == 404
        assert get_personal_info(db, theirs.id) is not None

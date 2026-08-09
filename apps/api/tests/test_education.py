from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.education import Education

FIELDS = ("name", "subheading", "duration", "location")


def payload(**overrides):
    body = {
        "name": "State University",
        "subheading": "BSc Computer Science",
        "duration": "2016 - 2020",
        "location": "Boston, MA",
    }
    body.update(overrides)
    return body


def education_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Education)) or 0


def get_education(db: Session, education_id: UUID) -> Education | None:
    db.expire_all()
    return db.get(Education, education_id)


class TestAuthentication:
    @pytest.mark.parametrize(
        ("method", "body"),
        [
            ("GET", None),
            ("POST", payload()),
            ("PUT", {"id": str(uuid4()), "name": "Renamed"}),
            ("DELETE", {"id": str(uuid4())}),
        ],
    )
    def test_requires_a_session_cookie(self, client: TestClient, method, body):
        response = client.request(method, "/education/", json=body)

        assert response.status_code == 401


class TestGet:
    def test_returns_an_empty_list_for_a_new_user(self, auth, user):
        response = auth(user).get("/education/")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_the_callers_educations(
        self, auth, user, other_user, make_education
    ):
        mine = make_education(user, name="Mine")
        make_education(other_user, name="Theirs")

        response = auth(user).get("/education/")

        assert [row["id"] for row in response.json()] == [str(mine.id)]

    def test_returns_every_field(self, auth, user, make_education):
        make_education(user)

        [row] = auth(user).get("/education/").json()

        assert row["name"] == "State University"
        assert row["subheading"] == "BSc Computer Science"
        assert row["duration"] == "2016 - 2020"
        assert row["location"] == "Boston, MA"

    def test_returns_all_of_the_callers_educations(self, auth, user, make_education):
        make_education(user, name="First")
        make_education(user, name="Second")

        response = auth(user).get("/education/")

        assert {row["name"] for row in response.json()} == {"First", "Second"}


class TestCreate:
    def test_creates_an_education(self, auth, user, db):
        response = auth(user).post("/education/", json=payload())

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "State University"
        assert body["subheading"] == "BSc Computer Science"
        assert body["duration"] == "2016 - 2020"
        assert body["location"] == "Boston, MA"

        created = get_education(db, UUID(body["id"]))
        assert created is not None
        assert created.user_id == user.id

    @pytest.mark.parametrize("field", FIELDS)
    def test_requires_every_field(self, auth, user, db, field):
        body = payload()
        del body[field]
        before = education_count(db)

        response = auth(user).post("/education/", json=body)

        assert response.status_code == 422
        assert education_count(db) == before

    @pytest.mark.parametrize("field", FIELDS)
    def test_rejects_a_null_field(self, auth, user, db, field):
        before = education_count(db)

        response = auth(user).post("/education/", json=payload(**{field: None}))

        assert response.status_code == 422
        assert education_count(db) == before

    @pytest.mark.parametrize("field", FIELDS)
    def test_rejects_an_overlong_field(self, auth, user, db, field):
        before = education_count(db)

        response = auth(user).post("/education/", json=payload(**{field: "a" * 256}))

        assert response.status_code == 422
        assert education_count(db) == before


class TestEdit:
    def test_updates_only_the_supplied_fields(self, auth, user, make_education, db):
        education = make_education(user, name="Old name", location="Boston, MA")

        response = auth(user).put(
            "/education/", json={"id": str(education.id), "name": "New name"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "New name"
        assert body["location"] == "Boston, MA"

        updated = get_education(db, education.id)
        assert updated is not None
        assert updated.name == "New name"
        assert updated.location == "Boston, MA"

    def test_updates_every_field_at_once(self, auth, user, make_education, db):
        education = make_education(user)
        changes = payload(
            name="Other University",
            subheading="MSc Distributed Systems",
            duration="2020 - 2022",
            location="Seattle, WA",
        )

        response = auth(user).put(
            "/education/", json={"id": str(education.id)} | changes
        )

        assert response.status_code == 200
        for field, value in changes.items():
            assert response.json()[field] == value

        updated = get_education(db, education.id)
        assert updated is not None
        assert updated.subheading == "MSc Distributed Systems"

    @pytest.mark.parametrize("field", FIELDS)
    def test_rejects_a_null_field(self, auth, user, make_education, db, field):
        # The columns are NOT NULL: a null has to fail validation rather than
        # reach the database and blow up as an IntegrityError.
        education = make_education(user)

        response = auth(user).put(
            "/education/", json={"id": str(education.id), field: None}
        )

        assert response.status_code == 422

        untouched = get_education(db, education.id)
        assert untouched is not None
        assert getattr(untouched, field) == getattr(education, field)

    def test_rejects_an_update_with_no_fields(self, auth, user, make_education):
        education = make_education(user)

        response = auth(user).put("/education/", json={"id": str(education.id)})

        assert response.status_code == 400

    def test_cannot_edit_another_users_education(
        self, auth, user, other_user, make_education, db
    ):
        education = make_education(other_user, name="Theirs")

        response = auth(user).put(
            "/education/", json={"id": str(education.id), "name": "Hijacked"}
        )

        assert response.status_code == 404

        untouched = get_education(db, education.id)
        assert untouched is not None
        assert untouched.name == "Theirs"

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).put(
            "/education/", json={"id": str(uuid4()), "name": "Ghost"}
        )

        assert response.status_code == 404


class TestDelete:
    def test_deletes_the_education(self, auth, user, make_education, db):
        education = make_education(user, name="State University")

        response = auth(user).request(
            "DELETE", "/education/", json={"id": str(education.id)}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "State University"
        assert get_education(db, education.id) is None

    def test_leaves_other_rows_alone(self, auth, user, make_education, db):
        education = make_education(user, name="Doomed")
        survivor = make_education(user, name="Survivor")

        auth(user).request("DELETE", "/education/", json={"id": str(education.id)})

        assert get_education(db, survivor.id) is not None

    def test_cannot_delete_another_users_education(
        self, auth, user, other_user, make_education, db
    ):
        education = make_education(other_user)

        response = auth(user).request(
            "DELETE", "/education/", json={"id": str(education.id)}
        )

        assert response.status_code == 404
        assert get_education(db, education.id) is not None

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).request(
            "DELETE", "/education/", json={"id": str(uuid4())}
        )

        assert response.status_code == 404

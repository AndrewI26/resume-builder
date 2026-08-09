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
        ("method", "path", "body"),
        [
            ("GET", "/education/", None),
            ("POST", "/education/", payload()),
            ("GET", f"/education/{uuid4()}", None),
            ("PUT", f"/education/{uuid4()}", {"name": "Renamed"}),
            ("DELETE", f"/education/{uuid4()}", None),
        ],
    )
    def test_requires_a_session_cookie(self, client: TestClient, method, path, body):
        response = client.request(method, path, json=body)

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


class TestGetOne:
    def test_returns_the_education(self, auth, user, make_education):
        education = make_education(user)

        response = auth(user).get(f"/education/{education.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(education.id)
        assert body["name"] == "State University"
        assert body["subheading"] == "BSc Computer Science"
        assert body["duration"] == "2016 - 2020"
        assert body["location"] == "Boston, MA"

    def test_returns_the_addressed_row(self, auth, user, make_education):
        make_education(user, name="First")
        wanted = make_education(user, name="Second")

        response = auth(user).get(f"/education/{wanted.id}")

        assert response.json()["name"] == "Second"

    def test_requires_a_session_cookie(self, client, make_education, user):
        education = make_education(user)

        assert client.get(f"/education/{education.id}").status_code == 401

    def test_returns_404_for_an_unknown_id(self, auth, user):
        assert auth(user).get(f"/education/{uuid4()}").status_code == 404

    def test_cannot_read_another_users_education(
        self, auth, user, other_user, make_education
    ):
        education = make_education(other_user)

        assert auth(user).get(f"/education/{education.id}").status_code == 404

    def test_rejects_a_malformed_id(self, auth, user):
        assert auth(user).get("/education/not-a-uuid").status_code == 422


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
            f"/education/{education.id}", json={"name": "New name"}
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

        response = auth(user).put(f"/education/{education.id}", json=changes)

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

        response = auth(user).put(f"/education/{education.id}", json={field: None})

        assert response.status_code == 422

        untouched = get_education(db, education.id)
        assert untouched is not None
        assert getattr(untouched, field) == getattr(education, field)

    def test_rejects_an_update_with_no_fields(self, auth, user, make_education):
        education = make_education(user)

        response = auth(user).put(f"/education/{education.id}", json={})

        assert response.status_code == 400

    def test_cannot_edit_another_users_education(
        self, auth, user, other_user, make_education, db
    ):
        education = make_education(other_user, name="Theirs")

        response = auth(user).put(
            f"/education/{education.id}", json={"name": "Hijacked"}
        )

        assert response.status_code == 404

        untouched = get_education(db, education.id)
        assert untouched is not None
        assert untouched.name == "Theirs"

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).put(f"/education/{uuid4()}", json={"name": "Ghost"})

        assert response.status_code == 404


class TestDelete:
    def test_deletes_the_education(self, auth, user, make_education, db):
        education = make_education(user, name="State University")

        response = auth(user).delete(f"/education/{education.id}")

        assert response.status_code == 200
        assert response.json()["name"] == "State University"
        assert get_education(db, education.id) is None

    def test_leaves_other_rows_alone(self, auth, user, make_education, db):
        education = make_education(user, name="Doomed")
        survivor = make_education(user, name="Survivor")

        auth(user).delete(f"/education/{education.id}")

        assert get_education(db, survivor.id) is not None

    def test_cannot_delete_another_users_education(
        self, auth, user, other_user, make_education, db
    ):
        education = make_education(other_user)

        response = auth(user).delete(f"/education/{education.id}")

        assert response.status_code == 404
        assert get_education(db, education.id) is not None

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).delete(f"/education/{uuid4()}")

        assert response.status_code == 404

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.skill import Skill

LANGUAGES = [
    "TypeScript/JavaScript",
    "Python",
    "Go",
    "C",
    "C++",
    "Racket",
    "Haskell",
    "SQL",
    "HTML/CSS",
]


def payload(**overrides):
    body = {"name": "Languages", "items": LANGUAGES}
    body.update(overrides)
    return body


def skill_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Skill)) or 0


def get_skill(db: Session, skill_id: UUID) -> Skill | None:
    db.expire_all()
    return db.get(Skill, skill_id)


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
        response = client.request(method, "/skill/", json=body)

        assert response.status_code == 401


class TestGet:
    def test_returns_an_empty_list_for_a_new_user(self, auth, user):
        response = auth(user).get("/skill/")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_the_callers_skills(self, auth, user, other_user, make_skill):
        mine = make_skill(user, name="Mine")
        make_skill(other_user, name="Theirs")

        response = auth(user).get("/skill/")

        assert [row["id"] for row in response.json()] == [str(mine.id)]

    def test_returns_lists_ordered_by_position(self, auth, user, make_skill):
        make_skill(user, name="Third", position=2)
        make_skill(user, name="First", position=0)
        make_skill(user, name="Second", position=1)

        response = auth(user).get("/skill/")

        assert [row["name"] for row in response.json()] == [
            "First",
            "Second",
            "Third",
        ]

    def test_preserves_item_order(self, auth, user, make_skill):
        make_skill(user, items=LANGUAGES)

        [row] = auth(user).get("/skill/").json()

        assert row["items"] == LANGUAGES


class TestGetOne:
    def test_returns_the_skill_list(self, auth, user, make_skill):
        skill = make_skill(user, name="Languages", items=LANGUAGES, position=3)

        response = auth(user).get(f"/skill/{skill.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(skill.id)
        assert body["name"] == "Languages"
        assert body["items"] == LANGUAGES
        assert body["position"] == 3

    def test_returns_the_addressed_row(self, auth, user, make_skill):
        make_skill(user, name="Languages", position=0)
        wanted = make_skill(user, name="Technologies/Frameworks", position=1)

        response = auth(user).get(f"/skill/{wanted.id}")

        assert response.json()["name"] == "Technologies/Frameworks"

    def test_requires_a_session_cookie(self, client, make_skill, user):
        skill = make_skill(user)

        assert client.get(f"/skill/{skill.id}").status_code == 401

    def test_returns_404_for_an_unknown_id(self, auth, user):
        assert auth(user).get(f"/skill/{uuid4()}").status_code == 404

    def test_cannot_read_another_users_skill(self, auth, user, other_user, make_skill):
        skill = make_skill(other_user)

        assert auth(user).get(f"/skill/{skill.id}").status_code == 404

    def test_rejects_a_malformed_id(self, auth, user):
        assert auth(user).get("/skill/not-a-uuid").status_code == 422


class TestCreate:
    def test_creates_a_skill_list(self, auth, user, db):
        response = auth(user).post("/skill/", json=payload())

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Languages"
        assert body["items"] == LANGUAGES

        created = get_skill(db, UUID(body["id"]))
        assert created is not None
        assert created.user_id == user.id
        assert created.items == LANGUAGES

    def test_first_list_is_position_zero(self, auth, user):
        response = auth(user).post("/skill/", json=payload())

        assert response.json()["position"] == 0

    def test_appends_after_the_callers_existing_lists(self, auth, user, make_skill):
        make_skill(user, name="Languages", position=0)
        make_skill(user, name="Technologies/Frameworks", position=1)

        response = auth(user).post("/skill/", json=payload(name="Tools"))

        assert response.json()["position"] == 2

    def test_append_ignores_other_users_lists(self, auth, user, other_user, make_skill):
        make_skill(other_user, position=7)

        response = auth(user).post("/skill/", json=payload())

        assert response.json()["position"] == 0

    def test_honours_an_explicit_position(self, auth, user, make_skill):
        make_skill(user, position=0)

        response = auth(user).post("/skill/", json=payload(position=5))

        assert response.json()["position"] == 5

    def test_accepts_an_empty_item_list(self, auth, user):
        response = auth(user).post("/skill/", json=payload(items=[]))

        assert response.status_code == 201
        assert response.json()["items"] == []

    @pytest.mark.parametrize(
        ("description", "body"),
        [
            ("missing name", {"items": ["Python"]}),
            ("missing items", {"name": "Languages"}),
            ("null name", payload(name=None)),
            ("null items", payload(items=None)),
            ("overlong name", payload(name="a" * 256)),
            ("overlong item", payload(items=["a" * 256])),
            ("negative position", payload(position=-1)),
        ],
    )
    def test_rejects_invalid_payloads(self, auth, user, db, description, body):
        before = skill_count(db)

        response = auth(user).post("/skill/", json=body)

        assert response.status_code == 422, description
        assert skill_count(db) == before


class TestEdit:
    def test_renames_a_list(self, auth, user, make_skill, db):
        skill = make_skill(user, name="Languages", items=["Python"])

        response = auth(user).put(
            "/skill/", json={"id": str(skill.id), "name": "Programming Languages"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Programming Languages"
        assert body["items"] == ["Python"]

        updated = get_skill(db, skill.id)
        assert updated is not None
        assert updated.name == "Programming Languages"

    def test_replaces_the_items(self, auth, user, make_skill, db):
        skill = make_skill(user, items=["Python", "Go"])

        response = auth(user).put(
            "/skill/", json={"id": str(skill.id), "items": ["Rust", "Zig", "C"]}
        )

        assert response.json()["items"] == ["Rust", "Zig", "C"]

        updated = get_skill(db, skill.id)
        assert updated is not None
        assert updated.items == ["Rust", "Zig", "C"]

    def test_reorders_the_items(self, auth, user, make_skill):
        skill = make_skill(user, items=["Python", "Go", "SQL"])
        reordered = ["SQL", "Python", "Go"]

        response = auth(user).put(
            "/skill/", json={"id": str(skill.id), "items": reordered}
        )

        assert response.json()["items"] == reordered

    def test_can_empty_the_items(self, auth, user, make_skill):
        skill = make_skill(user, items=["Python"])

        response = auth(user).put("/skill/", json={"id": str(skill.id), "items": []})

        assert response.json()["items"] == []

    def test_reorders_the_lists(self, auth, user, make_skill):
        languages = make_skill(user, name="Languages", position=0)
        frameworks = make_skill(user, name="Technologies/Frameworks", position=1)

        client = auth(user)
        client.put("/skill/", json={"id": str(languages.id), "position": 1})
        client.put("/skill/", json={"id": str(frameworks.id), "position": 0})

        assert [row["name"] for row in client.get("/skill/").json()] == [
            "Technologies/Frameworks",
            "Languages",
        ]

    @pytest.mark.parametrize("field", ["name", "items", "position"])
    def test_rejects_a_null_field(self, auth, user, make_skill, db, field):
        # Every column is NOT NULL: null has to fail validation rather than
        # reach the database as an IntegrityError.
        skill = make_skill(user)

        response = auth(user).put("/skill/", json={"id": str(skill.id), field: None})

        assert response.status_code == 422

        untouched = get_skill(db, skill.id)
        assert untouched is not None
        assert getattr(untouched, field) == getattr(skill, field)

    def test_rejects_a_negative_position(self, auth, user, make_skill):
        skill = make_skill(user, position=3)

        response = auth(user).put("/skill/", json={"id": str(skill.id), "position": -1})

        assert response.status_code == 422

    def test_rejects_an_update_with_no_fields(self, auth, user, make_skill):
        skill = make_skill(user)

        response = auth(user).put("/skill/", json={"id": str(skill.id)})

        assert response.status_code == 400

    def test_cannot_edit_another_users_skill(
        self, auth, user, other_user, make_skill, db
    ):
        skill = make_skill(other_user, name="Theirs")

        response = auth(user).put(
            "/skill/", json={"id": str(skill.id), "name": "Hijacked"}
        )

        assert response.status_code == 404

        untouched = get_skill(db, skill.id)
        assert untouched is not None
        assert untouched.name == "Theirs"

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).put("/skill/", json={"id": str(uuid4()), "name": "Ghost"})

        assert response.status_code == 404


class TestDelete:
    def test_deletes_the_skill_list(self, auth, user, make_skill, db):
        skill = make_skill(user, name="Languages")

        response = auth(user).request("DELETE", "/skill/", json={"id": str(skill.id)})

        assert response.status_code == 200
        assert response.json()["name"] == "Languages"
        assert get_skill(db, skill.id) is None

    def test_returns_the_deleted_items(self, auth, user, make_skill):
        skill = make_skill(user, items=LANGUAGES)

        response = auth(user).request("DELETE", "/skill/", json={"id": str(skill.id)})

        assert response.json()["items"] == LANGUAGES

    def test_leaves_other_lists_alone(self, auth, user, make_skill, db):
        doomed = make_skill(user, name="Doomed", position=0)
        survivor = make_skill(user, name="Survivor", position=1)

        auth(user).request("DELETE", "/skill/", json={"id": str(doomed.id)})

        assert get_skill(db, survivor.id) is not None

    def test_cannot_delete_another_users_skill(
        self, auth, user, other_user, make_skill, db
    ):
        skill = make_skill(other_user)

        response = auth(user).request("DELETE", "/skill/", json={"id": str(skill.id)})

        assert response.status_code == 404
        assert get_skill(db, skill.id) is not None

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).request("DELETE", "/skill/", json={"id": str(uuid4())})

        assert response.status_code == 404

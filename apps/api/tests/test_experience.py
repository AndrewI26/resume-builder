from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.bullet_points import BulletPoint
from models.expirence import Expirence


def payload(**overrides):
    body = {
        "company": "Acme",
        "position": "Engineer",
        "duration": "2020 - 2022",
        "location": "New York, NY",
        "bullet_points": [
            {"text": "Shipped the thing", "bolded": [[0, 6]]},
            {"text": "Shipped another thing", "bolded": []},
        ],
    }
    body.update(overrides)
    return body


def bullet_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(BulletPoint)) or 0


def get_expirence(db: Session, expirence_id: UUID) -> Expirence | None:
    db.expire_all()
    return db.get(Expirence, expirence_id)


class TestAuthentication:
    @pytest.mark.parametrize(
        ("method", "body"),
        [
            ("GET", None),
            ("POST", payload()),
            ("PUT", {"id": str(uuid4()), "company": "Acme"}),
            ("DELETE", {"id": str(uuid4())}),
        ],
    )
    def test_requires_a_session_cookie(self, client: TestClient, method, body):
        response = client.request(method, "/experience/", json=body)

        assert response.status_code == 401

    def test_rejects_a_garbage_cookie(self, client: TestClient):
        client.cookies.set("access_token", "not-a-jwt")

        assert client.get("/experience/").status_code == 401


class TestGet:
    def test_returns_an_empty_list_for_a_new_user(self, auth, user):
        response = auth(user).get("/experience/")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_the_callers_experiences(
        self, auth, user, other_user, make_expirence
    ):
        mine = make_expirence(user, company="Mine")
        make_expirence(other_user, company="Theirs")

        response = auth(user).get("/experience/")

        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [str(mine.id)]

    def test_hydrates_bullet_points_in_stored_order(self, auth, user, make_expirence):
        make_expirence(user, bullets=("Alpha", "Beta", "Gamma"))

        response = auth(user).get("/experience/")

        [row] = response.json()
        assert [bullet["text"] for bullet in row["bullet_points"]] == [
            "Alpha",
            "Beta",
            "Gamma",
        ]


class TestGetOne:
    def test_returns_the_experience(self, auth, user, make_expirence):
        expirence = make_expirence(user, company="Acme", position="Engineer")

        response = auth(user).get(f"/experience/{expirence.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(expirence.id)
        assert body["company"] == "Acme"
        assert body["position"] == "Engineer"

    def test_hydrates_bullet_points_in_stored_order(self, auth, user, make_expirence):
        expirence = make_expirence(user, bullets=("Alpha", "Beta", "Gamma"))

        response = auth(user).get(f"/experience/{expirence.id}")

        assert [b["text"] for b in response.json()["bullet_points"]] == [
            "Alpha",
            "Beta",
            "Gamma",
        ]

    def test_returns_the_addressed_row(self, auth, user, make_expirence):
        make_expirence(user, company="First")
        wanted = make_expirence(user, company="Second")

        response = auth(user).get(f"/experience/{wanted.id}")

        assert response.json()["company"] == "Second"

    def test_requires_a_session_cookie(self, client, make_expirence, user):
        expirence = make_expirence(user)

        assert client.get(f"/experience/{expirence.id}").status_code == 401

    def test_returns_404_for_an_unknown_id(self, auth, user):
        assert auth(user).get(f"/experience/{uuid4()}").status_code == 404

    def test_cannot_read_another_users_experience(
        self, auth, user, other_user, make_expirence
    ):
        expirence = make_expirence(other_user)

        assert auth(user).get(f"/experience/{expirence.id}").status_code == 404

    def test_rejects_a_malformed_id(self, auth, user):
        assert auth(user).get("/experience/not-a-uuid").status_code == 422


class TestCreate:
    def test_creates_an_experience(self, auth, user, db):
        response = auth(user).post("/experience/", json=payload())

        assert response.status_code == 201
        body = response.json()
        assert body["company"] == "Acme"
        assert body["position"] == "Engineer"

        created = get_expirence(db, UUID(body["id"]))
        assert created is not None
        assert created.user_id == user.id

    def test_returns_and_stores_bullet_points_in_submitted_order(self, auth, user, db):
        bullets = [{"text": f"Bullet {index}", "bolded": []} for index in range(10)]

        response = auth(user).post("/experience/", json=payload(bullet_points=bullets))

        assert response.status_code == 201
        body = response.json()
        expected = [bullet["text"] for bullet in bullets]
        assert [bullet["text"] for bullet in body["bullet_points"]] == expected

        # The stored id array must match that order too, not just the response.
        created = get_expirence(db, UUID(body["id"]))
        assert created is not None
        stored = {
            row.id: row.text
            for row in db.scalars(
                select(BulletPoint).where(BulletPoint.id.in_(created.bullet_points))
            )
        }
        assert [stored[id] for id in created.bullet_points] == expected

    def test_persists_bullet_point_rows(self, auth, user, db):
        before = bullet_count(db)

        auth(user).post("/experience/", json=payload())

        assert bullet_count(db) == before + 2

    def test_preserves_bolded_ranges(self, auth, user):
        body = payload(bullet_points=[{"text": "Shipped it", "bolded": [[0, 6]]}])

        response = auth(user).post("/experience/", json=body)

        assert response.json()["bullet_points"][0]["bolded"] == [[0, 6]]

    def test_accepts_an_experience_with_no_bullet_points(self, auth, user):
        response = auth(user).post("/experience/", json=payload(bullet_points=[]))

        assert response.status_code == 201
        assert response.json()["bullet_points"] == []

    @pytest.mark.parametrize(
        "bolded",
        [
            [[5, 2]],  # start after end
            [[-1, 3]],  # negative
            [[0, 99]],  # past the end of the text
        ],
    )
    def test_rejects_out_of_range_bolded_coordinates(self, auth, user, db, bolded):
        before = bullet_count(db)
        body = payload(bullet_points=[{"text": "Short text", "bolded": bolded}])

        response = auth(user).post("/experience/", json=body)

        assert response.status_code == 422
        assert bullet_count(db) == before


class TestEdit:
    def test_updates_only_the_supplied_fields(self, auth, user, make_expirence, db):
        expirence = make_expirence(user, company="Acme", position="Engineer")

        response = auth(user).put(
            "/experience/", json={"id": str(expirence.id), "company": "Globex"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["company"] == "Globex"
        assert body["position"] == "Engineer"
        assert [bullet["text"] for bullet in body["bullet_points"]] == [
            "First bullet",
            "Second bullet",
        ]

        updated = get_expirence(db, expirence.id)
        assert updated is not None
        assert updated.company == "Globex"

    def test_replaces_bullet_points_and_removes_the_old_rows(
        self, auth, user, make_expirence, db
    ):
        expirence = make_expirence(user, bullets=("Old one", "Old two"))
        stale_ids = list(expirence.bullet_points)

        response = auth(user).put(
            "/experience/",
            json={
                "id": str(expirence.id),
                "bullet_points": [{"text": "Brand new", "bolded": []}],
            },
        )

        assert response.status_code == 200
        assert [b["text"] for b in response.json()["bullet_points"]] == ["Brand new"]

        orphans = db.scalars(
            select(BulletPoint).where(BulletPoint.id.in_(stale_ids))
        ).all()
        assert orphans == []

    def test_rejects_an_update_with_no_fields(self, auth, user, make_expirence):
        expirence = make_expirence(user)

        response = auth(user).put("/experience/", json={"id": str(expirence.id)})

        assert response.status_code == 400

    def test_cannot_edit_another_users_experience(
        self, auth, user, other_user, make_expirence, db
    ):
        expirence = make_expirence(other_user, company="Theirs")

        response = auth(user).put(
            "/experience/", json={"id": str(expirence.id), "company": "Hijacked"}
        )

        assert response.status_code == 404

        untouched = get_expirence(db, expirence.id)
        assert untouched is not None
        assert untouched.company == "Theirs"

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).put(
            "/experience/", json={"id": str(uuid4()), "company": "Ghost"}
        )

        assert response.status_code == 404


class TestDelete:
    def test_deletes_the_experience(self, auth, user, make_expirence, db):
        expirence = make_expirence(user, company="Acme")

        response = auth(user).request(
            "DELETE", "/experience/", json={"id": str(expirence.id)}
        )

        assert response.status_code == 200
        assert response.json()["company"] == "Acme"
        assert get_expirence(db, expirence.id) is None

    def test_returns_the_deleted_experience_with_its_bullet_points(
        self, auth, user, make_expirence
    ):
        expirence = make_expirence(user, bullets=("Alpha", "Beta"))

        response = auth(user).request(
            "DELETE", "/experience/", json={"id": str(expirence.id)}
        )

        assert [b["text"] for b in response.json()["bullet_points"]] == [
            "Alpha",
            "Beta",
        ]

    def test_removes_the_orphaned_bullet_point_rows(
        self, auth, user, make_expirence, db
    ):
        expirence = make_expirence(user, bullets=("Alpha", "Beta"))
        bullet_ids = list(expirence.bullet_points)

        auth(user).request("DELETE", "/experience/", json={"id": str(expirence.id)})

        orphans = db.scalars(
            select(BulletPoint).where(BulletPoint.id.in_(bullet_ids))
        ).all()
        assert orphans == []

    def test_cannot_delete_another_users_experience(
        self, auth, user, other_user, make_expirence, db
    ):
        expirence = make_expirence(other_user)

        response = auth(user).request(
            "DELETE", "/experience/", json={"id": str(expirence.id)}
        )

        assert response.status_code == 404
        assert get_expirence(db, expirence.id) is not None

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).request(
            "DELETE", "/experience/", json={"id": str(uuid4())}
        )

        assert response.status_code == 404

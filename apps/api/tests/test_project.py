from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.bullet_points import BulletPoint
from models.project import Project


def payload(**overrides):
    body = {
        "name": "Resume Builder",
        "link": "https://example.com/project",
        "technologies": ["Python", "FastAPI"],
        "bullet_points": [
            {"text": "Shipped the thing", "bolded": [[0, 6]]},
            {"text": "Shipped another thing", "bolded": []},
        ],
    }
    body.update(overrides)
    return body


def bullet_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(BulletPoint)) or 0


def get_project(db: Session, project_id: UUID) -> Project | None:
    db.expire_all()
    return db.get(Project, project_id)


class TestAuthentication:
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("GET", "/project/", None),
            ("POST", "/project/", payload()),
            ("GET", f"/project/{uuid4()}", None),
            ("PUT", f"/project/{uuid4()}", {"name": "Renamed"}),
            ("DELETE", f"/project/{uuid4()}", None),
        ],
    )
    def test_requires_a_session_cookie(self, client: TestClient, method, path, body):
        response = client.request(method, path, json=body)

        assert response.status_code == 401


class TestGet:
    def test_returns_an_empty_list_for_a_new_user(self, auth, user):
        response = auth(user).get("/project/")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_the_callers_projects(
        self, auth, user, other_user, make_project
    ):
        mine = make_project(user, name="Mine")
        make_project(other_user, name="Theirs")

        response = auth(user).get("/project/")

        assert [row["id"] for row in response.json()] == [str(mine.id)]

    def test_hydrates_bullet_points_in_stored_order(self, auth, user, make_project):
        make_project(user, bullets=("Alpha", "Beta", "Gamma"))

        response = auth(user).get("/project/")

        [row] = response.json()
        assert [bullet["text"] for bullet in row["bullet_points"]] == [
            "Alpha",
            "Beta",
            "Gamma",
        ]

    def test_returns_technologies_in_stored_order(self, auth, user, make_project):
        make_project(user, technologies=("Rust", "Axum", "Postgres"))

        response = auth(user).get("/project/")

        [row] = response.json()
        assert row["technologies"] == ["Rust", "Axum", "Postgres"]


class TestGetOne:
    def test_returns_the_project(self, auth, user, make_project):
        project = make_project(user, name="Resume Builder")

        response = auth(user).get(f"/project/{project.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(project.id)
        assert body["name"] == "Resume Builder"
        assert body["technologies"] == ["Python", "FastAPI"]

    def test_hydrates_bullet_points_in_stored_order(self, auth, user, make_project):
        project = make_project(user, bullets=("Alpha", "Beta", "Gamma"))

        response = auth(user).get(f"/project/{project.id}")

        assert [b["text"] for b in response.json()["bullet_points"]] == [
            "Alpha",
            "Beta",
            "Gamma",
        ]

    def test_returns_the_addressed_row(self, auth, user, make_project):
        make_project(user, name="First")
        wanted = make_project(user, name="Second")

        response = auth(user).get(f"/project/{wanted.id}")

        assert response.json()["name"] == "Second"

    def test_requires_a_session_cookie(self, client, make_project, user):
        project = make_project(user)

        assert client.get(f"/project/{project.id}").status_code == 401

    def test_returns_404_for_an_unknown_id(self, auth, user):
        assert auth(user).get(f"/project/{uuid4()}").status_code == 404

    def test_cannot_read_another_users_project(
        self, auth, user, other_user, make_project
    ):
        project = make_project(other_user)

        assert auth(user).get(f"/project/{project.id}").status_code == 404

    def test_rejects_a_malformed_id(self, auth, user):
        assert auth(user).get("/project/not-a-uuid").status_code == 422


class TestCreate:
    def test_creates_a_project(self, auth, user, db):
        response = auth(user).post("/project/", json=payload())

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Resume Builder"
        assert body["link"] == "https://example.com/project"
        assert body["technologies"] == ["Python", "FastAPI"]

        created = get_project(db, UUID(body["id"]))
        assert created is not None
        assert created.user_id == user.id

    def test_stores_bullet_points_in_submitted_order(self, auth, user, db):
        bullets = [{"text": f"Bullet {index}", "bolded": []} for index in range(10)]

        response = auth(user).post("/project/", json=payload(bullet_points=bullets))

        expected = [bullet["text"] for bullet in bullets]
        assert [b["text"] for b in response.json()["bullet_points"]] == expected

        created = get_project(db, UUID(response.json()["id"]))
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

        auth(user).post("/project/", json=payload())

        assert bullet_count(db) == before + 2

    def test_link_is_optional(self, auth, user, db):
        body = payload()
        del body["link"]

        response = auth(user).post("/project/", json=body)

        assert response.status_code == 201
        assert response.json()["link"] is None

        created = get_project(db, UUID(response.json()["id"]))
        assert created is not None
        assert created.link is None

    def test_accepts_an_explicit_null_link(self, auth, user):
        response = auth(user).post("/project/", json=payload(link=None))

        assert response.status_code == 201
        assert response.json()["link"] is None

    def test_accepts_empty_technologies_and_bullet_points(self, auth, user):
        response = auth(user).post(
            "/project/", json=payload(technologies=[], bullet_points=[])
        )

        assert response.status_code == 201
        assert response.json()["technologies"] == []
        assert response.json()["bullet_points"] == []

    @pytest.mark.parametrize(
        "body",
        [
            payload(name="a" * 256),
            payload(technologies=["a" * 256]),
            payload(link="a" * 2049),
            payload(bullet_points=[{"text": "Short", "bolded": [[0, 99]]}]),
        ],
    )
    def test_rejects_invalid_payloads(self, auth, user, db, body):
        before = bullet_count(db)

        response = auth(user).post("/project/", json=body)

        assert response.status_code == 422
        assert bullet_count(db) == before


class TestEdit:
    def test_updates_only_the_supplied_fields(self, auth, user, make_project, db):
        project = make_project(user, name="Old name", technologies=("Python",))

        response = auth(user).put(f"/project/{project.id}", json={"name": "New name"})

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "New name"
        assert body["technologies"] == ["Python"]
        assert [b["text"] for b in body["bullet_points"]] == [
            "First bullet",
            "Second bullet",
        ]

        updated = get_project(db, project.id)
        assert updated is not None
        assert updated.name == "New name"

    def test_replaces_technologies(self, auth, user, make_project):
        project = make_project(user, technologies=("Python", "FastAPI"))

        response = auth(user).put(
            f"/project/{project.id}", json={"technologies": ["Go"]}
        )

        assert response.json()["technologies"] == ["Go"]

    def test_rejects_an_explicit_null_link(self, auth, user, make_project, db):
        project = make_project(user, link="https://example.com/project")

        response = auth(user).put(f"/project/{project.id}", json={"link": None})

        assert response.status_code == 422

        untouched = get_project(db, project.id)
        assert untouched is not None
        assert untouched.link == "https://example.com/project"

    def test_omitting_the_link_leaves_it_unchanged(self, auth, user, make_project, db):
        project = make_project(user, link="https://example.com/project")

        response = auth(user).put(f"/project/{project.id}", json={"name": "Renamed"})

        assert response.status_code == 200
        assert response.json()["link"] == "https://example.com/project"

        updated = get_project(db, project.id)
        assert updated is not None
        assert updated.link == "https://example.com/project"

    def test_updates_the_link_when_given_a_string(self, auth, user, make_project, db):
        project = make_project(user, link="https://example.com/old")

        response = auth(user).put(
            f"/project/{project.id}", json={"link": "https://example.com/new"}
        )

        assert response.status_code == 200
        assert response.json()["link"] == "https://example.com/new"

        updated = get_project(db, project.id)
        assert updated is not None
        assert updated.link == "https://example.com/new"

    def test_replaces_bullet_points_and_removes_the_old_rows(
        self, auth, user, make_project, db
    ):
        project = make_project(user, bullets=("Old one", "Old two"))
        stale_ids = list(project.bullet_points)

        response = auth(user).put(
            f"/project/{project.id}",
            json={"bullet_points": [{"text": "Brand new", "bolded": []}]},
        )

        assert [b["text"] for b in response.json()["bullet_points"]] == ["Brand new"]

        orphans = db.scalars(
            select(BulletPoint).where(BulletPoint.id.in_(stale_ids))
        ).all()
        assert orphans == []

    def test_rejects_an_update_with_no_fields(self, auth, user, make_project):
        project = make_project(user)

        response = auth(user).put(f"/project/{project.id}", json={})

        assert response.status_code == 400

    def test_cannot_edit_another_users_project(
        self, auth, user, other_user, make_project, db
    ):
        project = make_project(other_user, name="Theirs")

        response = auth(user).put(f"/project/{project.id}", json={"name": "Hijacked"})

        assert response.status_code == 404

        untouched = get_project(db, project.id)
        assert untouched is not None
        assert untouched.name == "Theirs"

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).put(f"/project/{uuid4()}", json={"name": "Ghost"})

        assert response.status_code == 404


class TestDelete:
    def test_deletes_the_project(self, auth, user, make_project, db):
        project = make_project(user, name="Resume Builder")

        response = auth(user).delete(f"/project/{project.id}")

        assert response.status_code == 200
        assert response.json()["name"] == "Resume Builder"
        assert get_project(db, project.id) is None

    def test_returns_the_deleted_project_with_its_bullet_points(
        self, auth, user, make_project
    ):
        project = make_project(user, bullets=("Alpha", "Beta"))

        response = auth(user).delete(f"/project/{project.id}")

        assert [b["text"] for b in response.json()["bullet_points"]] == [
            "Alpha",
            "Beta",
        ]

    def test_removes_the_orphaned_bullet_point_rows(self, auth, user, make_project, db):
        project = make_project(user, bullets=("Alpha", "Beta"))
        bullet_ids = list(project.bullet_points)

        auth(user).delete(f"/project/{project.id}")

        orphans = db.scalars(
            select(BulletPoint).where(BulletPoint.id.in_(bullet_ids))
        ).all()
        assert orphans == []

    def test_cannot_delete_another_users_project(
        self, auth, user, other_user, make_project, db
    ):
        project = make_project(other_user)

        response = auth(user).delete(f"/project/{project.id}")

        assert response.status_code == 404
        assert get_project(db, project.id) is not None

    def test_returns_404_for_an_unknown_id(self, auth, user):
        response = auth(user).delete(f"/project/{uuid4()}")

        assert response.status_code == 404

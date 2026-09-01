from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import get_settings
from models.user import User
from services.security import ACCESS_TOKEN_COOKIE_NAME, verify_password

PASSWORD = "correct-horse-battery"

settings = get_settings()


def credentials(**overrides):
    body = {"email": "new@example.com", "password": PASSWORD}
    body.update(overrides)
    return body


def user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def token(payload: dict[str, Any], *, secret: str | None = None) -> str:
    return jwt.encode(
        payload, secret or settings.secret_key, algorithm=settings.jwt_algorithm
    )


def future() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=5)


class TestRegister:
    def test_creates_a_user(self, client: TestClient, db: Session):
        response = client.post("/auth/register", json=credentials())

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "new@example.com"

        created = db.get(User, UUID(body["id"]))
        assert created is not None
        assert created.email == "new@example.com"

    def test_stores_the_password_hashed(self, client: TestClient, db: Session):
        response = client.post("/auth/register", json=credentials())

        created = db.get(User, UUID(response.json()["id"]))
        assert created is not None
        # nullable since Google sign-in landed: password users must still have one
        assert created.hashed_password is not None
        assert created.hashed_password != PASSWORD
        assert verify_password(PASSWORD, created.hashed_password)

    def test_never_returns_the_password(self, client: TestClient):
        body = client.post("/auth/register", json=credentials()).json()

        assert "password" not in body
        assert "hashed_password" not in body

    def test_signs_the_new_user_in(self, client: TestClient):
        register = client.post("/auth/register", json=credentials())

        assert ACCESS_TOKEN_COOKIE_NAME in register.cookies

        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["id"] == register.json()["id"]

    def test_sets_an_httponly_lax_cookie(self, client: TestClient):
        response = client.post("/auth/register", json=credentials())

        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert "max-age" in cookie

    def test_rejects_a_duplicate_email(
        self, client: TestClient, db: Session, make_user
    ):
        make_user("taken@example.com")
        before = user_count(db)

        response = client.post(
            "/auth/register", json=credentials(email="taken@example.com")
        )

        assert response.status_code == 409
        assert user_count(db) == before

    def test_duplicate_email_does_not_sign_anyone_in(
        self, client: TestClient, make_user
    ):
        make_user("taken@example.com")

        client.post("/auth/register", json=credentials(email="taken@example.com"))

        assert client.get("/auth/me").status_code == 401

    @pytest.mark.parametrize(
        "body",
        [
            credentials(email="not-an-email"),
            credentials(password="short"),
            {"email": "new@example.com"},
            {"password": PASSWORD},
        ],
    )
    def test_rejects_invalid_payloads(self, client: TestClient, db: Session, body):
        before = user_count(db)

        response = client.post("/auth/register", json=body)

        assert response.status_code == 422
        assert user_count(db) == before


class TestLogin:
    def test_signs_in_with_correct_credentials(self, client: TestClient, make_user):
        user = make_user("me@example.com", password=PASSWORD)

        response = client.post(
            "/auth/login", json={"email": "me@example.com", "password": PASSWORD}
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(user.id)
        assert ACCESS_TOKEN_COOKIE_NAME in response.cookies

    def test_the_returned_cookie_authenticates(self, client: TestClient, make_user):
        make_user("me@example.com", password=PASSWORD)

        client.post(
            "/auth/login", json={"email": "me@example.com", "password": PASSWORD}
        )

        assert client.get("/auth/me").status_code == 200

    def test_rejects_a_wrong_password(self, client: TestClient, make_user):
        make_user("me@example.com", password=PASSWORD)

        response = client.post(
            "/auth/login", json={"email": "me@example.com", "password": "wrong"}
        )

        assert response.status_code == 401
        assert ACCESS_TOKEN_COOKIE_NAME not in response.cookies

    def test_rejects_an_unknown_email(self, client: TestClient):
        response = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
        )

        assert response.status_code == 401

    def test_gives_the_same_error_for_both_failures(
        self, client: TestClient, make_user
    ):
        make_user("me@example.com", password=PASSWORD)

        wrong_password = client.post(
            "/auth/login", json={"email": "me@example.com", "password": "wrong"}
        )
        unknown_email = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
        )

        # Diverging here would let an attacker enumerate registered emails.
        assert wrong_password.json() == unknown_email.json()


class TestLogout:
    def test_returns_no_content(self, client: TestClient, auth, user):
        auth(user)

        assert client.post("/auth/logout").status_code == 204

    def test_clears_the_session_cookie(self, client: TestClient, make_user):
        # Signs in for real rather than using the `auth` fixture: only a
        # server-set cookie can be matched and cleared by `delete_cookie`.
        make_user("me@example.com", password=PASSWORD)
        client.post(
            "/auth/login", json={"email": "me@example.com", "password": PASSWORD}
        )
        assert client.get("/auth/me").status_code == 200

        client.post("/auth/logout")

        assert ACCESS_TOKEN_COOKIE_NAME not in client.cookies
        assert client.get("/auth/me").status_code == 401

    def test_works_without_being_signed_in(self, client: TestClient):
        assert client.post("/auth/logout").status_code == 204


class TestMe:
    def test_returns_the_signed_in_user(self, auth, user):
        response = auth(user).get("/auth/me")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(user.id)
        assert body["email"] == user.email

    def test_reports_how_the_account_signs_in(self, auth, user):
        response = auth(user).get("/auth/me")

        assert response.json()["sign_in_methods"] == ["password"]

    def test_requires_a_cookie(self, client: TestClient):
        assert client.get("/auth/me").status_code == 401

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("malformed", "not-a-jwt"),
            ("empty", ""),
            (
                "wrong signing key",
                token(
                    {"sub": str(uuid4()), "exp": future()},
                    secret="a" * 64,
                ),
            ),
            (
                "expired",
                token(
                    {
                        "sub": str(uuid4()),
                        "exp": datetime.now(UTC) - timedelta(minutes=1),
                    }
                ),
            ),
            ("missing sub", token({"exp": future()})),
            ("sub is not a uuid", token({"sub": "nope", "exp": future()})),
        ],
    )
    def test_rejects_bad_tokens(self, client: TestClient, name, value):
        client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, value)

        assert client.get("/auth/me").status_code == 401, name

    def test_rejects_a_valid_token_for_a_deleted_user(
        self, client: TestClient, db: Session, user: User
    ):
        client.cookies.set(
            ACCESS_TOKEN_COOKIE_NAME, token({"sub": str(user.id), "exp": future()})
        )
        db.delete(user)
        db.commit()

        assert client.get("/auth/me").status_code == 401


class TestUpdateMe:
    def test_sets_the_name(self, auth, db: Session, user: User):
        response = auth(user).patch("/auth/me", json={"name": "Ada Lovelace"})

        assert response.status_code == 200
        assert response.json()["name"] == "Ada Lovelace"

        db.refresh(user)
        assert user.name == "Ada Lovelace"

    def test_trims_surrounding_whitespace(self, auth, user: User):
        response = auth(user).patch("/auth/me", json={"name": "  Ada  "})

        assert response.json()["name"] == "Ada"

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_an_empty_name_clears_it(self, auth, db: Session, user: User, value):
        user.name = "Ada"
        db.commit()

        response = auth(user).patch("/auth/me", json={"name": value})

        assert response.status_code == 200
        assert response.json()["name"] is None

        db.refresh(user)
        assert user.name is None

    def test_rejects_a_name_over_the_column_length(self, auth, user: User):
        response = auth(user).patch("/auth/me", json={"name": "a" * 256})

        assert response.status_code == 422

    def test_requires_a_cookie(self, client: TestClient):
        assert client.patch("/auth/me", json={"name": "Ada"}).status_code == 401

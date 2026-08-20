"""Google sign in.

Nothing here talks to Google: `google_oauth` is the seam, so its three
functions are replaced per test and what's left under test is the router's own
work — state handling, redirect safety, and how a verified profile maps onto a
local user.
"""

from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.oauth_account import GOOGLE_PROVIDER, OAuthAccount
from models.user import User
from routers import google_auth
from services.google_oauth import GoogleOAuthError, GoogleProfile
from services.security import (
    ACCESS_TOKEN_COOKIE_NAME,
    OAUTH_STATE_COOKIE_NAME,
    create_oauth_state_token,
    decode_access_token,
    decode_oauth_state_token,
)
from settings import get_settings

settings = get_settings()

STATE = "the-state"
NONCE = "the-nonce"
VERIFIER = "the-code-verifier"


PROFILE = GoogleProfile(
    sub="google-sub-1",
    email="someone@example.com",
    email_verified=True,
    name="Someone",
)


def profile(**overrides) -> GoogleProfile:
    return replace(PROFILE, **overrides)


def state_cookie(**overrides) -> str:
    claims = {
        "state": STATE,
        "nonce": NONCE,
        "code_verifier": VERIFIER,
        "next": "/",
    }
    claims.update(overrides)
    return create_oauth_state_token(claims)


def reloaded(db: Session, user: User) -> User:
    db.expire_all()
    row = db.get(User, user.id)
    assert row is not None
    return row


def user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def account_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(OAuthAccount)) or 0


def query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query)


@pytest.fixture
def no_redirects(client: TestClient) -> TestClient:
    client.follow_redirects = False
    return client


@pytest.fixture
def configured(monkeypatch) -> None:
    """Pretend the Google client credentials are set on this server."""
    monkeypatch.setattr(settings, "google_client_id", "client-id", raising=False)
    monkeypatch.setattr(settings, "google_client_secret", "secret", raising=False)


@pytest.fixture
def unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", None, raising=False)
    monkeypatch.setattr(settings, "google_client_secret", None, raising=False)


@pytest.fixture
def google(monkeypatch):
    """Replace the Google calls, returning a fixed profile by default."""

    def _google(
        *, returns: GoogleProfile | None = None, raises: Exception | None = None
    ):
        def _verify(id_token, *, expected_nonce=None):
            if raises is not None:
                raise raises
            return returns if returns is not None else profile()

        def _exchange(code, code_verifier):
            if raises is not None:
                raise raises
            return "an.id.token"

        monkeypatch.setattr(google_auth, "verify_id_token", _verify)
        monkeypatch.setattr(google_auth, "exchange_code_for_id_token", _exchange)

    return _google


class TestLoginRedirect:
    def test_is_unavailable_when_google_is_not_configured(
        self, no_redirects: TestClient, unconfigured
    ):
        response = no_redirects.get("/auth/google/login")

        assert response.status_code == 503

    def test_redirects_to_google(self, no_redirects: TestClient, configured):
        response = no_redirects.get("/auth/google/login")

        assert response.status_code == 307
        assert response.headers["location"].startswith(
            "https://accounts.google.com/o/oauth2/v2/auth?"
        )

    def test_asks_for_a_code_with_pkce(self, no_redirects: TestClient, configured):
        response = no_redirects.get("/auth/google/login")

        params = query(response.headers["location"])
        assert params["response_type"] == ["code"]
        assert params["code_challenge_method"] == ["S256"]
        assert params["client_id"] == ["client-id"]

    def test_sets_a_signed_handshake_cookie(self, no_redirects: TestClient, configured):
        response = no_redirects.get("/auth/google/login")

        stored = decode_oauth_state_token(response.cookies[OAUTH_STATE_COOKIE_NAME])
        assert stored is not None
        assert set(stored) >= {"state", "nonce", "code_verifier", "next"}

    def test_the_cookie_state_is_the_one_sent_to_google(
        self, no_redirects: TestClient, configured
    ):
        response = no_redirects.get("/auth/google/login")

        stored = decode_oauth_state_token(response.cookies[OAUTH_STATE_COOKIE_NAME])
        assert stored is not None
        assert query(response.headers["location"])["state"] == [stored["state"]]

    def test_the_cookie_is_httponly_and_scoped_to_the_callback(
        self, no_redirects: TestClient, configured
    ):
        response = no_redirects.get("/auth/google/login")

        header = response.headers["set-cookie"]
        assert "httponly" in header.lower()
        assert "path=/auth/google" in header.lower()

    def test_remembers_where_to_land_afterwards(
        self, no_redirects: TestClient, configured
    ):
        response = no_redirects.get("/auth/google/login", params={"next": "/dashboard"})

        stored = decode_oauth_state_token(response.cookies[OAUTH_STATE_COOKIE_NAME])
        assert stored is not None
        assert stored["next"] == "/dashboard"

    @pytest.mark.parametrize(
        "hostile", ["//evil.com", "https://evil.com", "/\\evil.com", "evil.com"]
    )
    def test_refuses_to_remember_an_offsite_redirect(
        self, no_redirects: TestClient, configured, hostile
    ):
        response = no_redirects.get("/auth/google/login", params={"next": hostile})

        stored = decode_oauth_state_token(response.cookies[OAUTH_STATE_COOKIE_NAME])
        assert stored is not None
        assert stored["next"] == "/"

    def test_reports_a_misconfigured_client(
        self, no_redirects: TestClient, configured, monkeypatch
    ):
        def _raise(**kwargs):
            raise GoogleOAuthError("GOOGLE_CLIENT_ID is not configured")

        monkeypatch.setattr(google_auth, "build_authorization_url", _raise)

        response = no_redirects.get("/auth/google/login")

        assert response.status_code == 503


class TestCallback:
    def test_signs_the_user_in(self, no_redirects: TestClient, db: Session, google):
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        assert response.status_code == 303
        signed_in = decode_access_token(response.cookies[ACCESS_TOKEN_COOKIE_NAME])
        assert signed_in == db.scalars(select(User.id)).one()

    def test_returns_to_the_remembered_path(self, no_redirects: TestClient, google):
        google()
        no_redirects.cookies.set(
            OAUTH_STATE_COOKIE_NAME, state_cookie(next="/dashboard")
        )

        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        assert response.headers["location"] == f"{settings.frontend_url}/dashboard"

    def test_creates_the_user_and_the_linked_account(
        self, no_redirects: TestClient, db: Session, google
    ):
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        db.expire_all()
        created = db.scalars(select(User)).one()
        account = db.scalars(select(OAuthAccount)).one()
        assert created.email == "someone@example.com"
        assert created.hashed_password is None
        assert account.provider == GOOGLE_PROVIDER
        assert account.provider_account_id == "google-sub-1"
        assert account.user_id == created.id

    def test_retires_the_handshake_cookie(self, no_redirects: TestClient, google):
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        assert OAUTH_STATE_COOKIE_NAME in response.headers["set-cookie"]
        assert 'oauth_state=""' in response.headers["set-cookie"]

    def test_a_returning_google_user_is_not_duplicated(
        self, no_redirects: TestClient, db: Session, google
    ):
        google()

        for _ in range(2):
            no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())
            no_redirects.get(
                "/auth/google/callback", params={"code": "the-code", "state": STATE}
            )

        assert user_count(db) == 1
        assert account_count(db) == 1

    def test_links_onto_a_local_account_with_the_same_email(
        self, no_redirects: TestClient, db: Session, google, make_user
    ):
        existing = make_user("someone@example.com", password="a-real-password")
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        db.expire_all()
        assert user_count(db) == 1
        assert db.scalars(select(OAuthAccount)).one().user_id == existing.id

    def test_linking_keeps_the_existing_password(
        self, no_redirects: TestClient, db: Session, google, make_user
    ):
        existing = make_user("someone@example.com", password="a-real-password")
        hashed = existing.hashed_password
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        assert reloaded(db, existing).hashed_password == hashed

    def test_fills_in_a_missing_display_name(
        self, no_redirects: TestClient, db: Session, google, make_user
    ):
        existing = make_user("someone@example.com")
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        assert reloaded(db, existing).name == "Someone"

    def test_never_overwrites_a_name_the_user_already_has(
        self, no_redirects: TestClient, db: Session, google, make_user
    ):
        existing = make_user("someone@example.com")
        existing.name = "Chosen Name"
        db.commit()
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        assert reloaded(db, existing).name == "Chosen Name"

    def test_refreshes_the_email_recorded_on_the_link(
        self, no_redirects: TestClient, db: Session, google
    ):
        google()
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())
        no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        google(returns=profile(email="renamed@example.com"))
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())
        no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        db.expire_all()
        assert db.scalars(select(OAuthAccount)).one().email == "renamed@example.com"


class TestCallbackFailures:
    """Failures are browser navigations, so they redirect rather than 4xx."""

    def _assert_rejected(self, response, reason: str):
        assert response.status_code == 303
        assert query(response.headers["location"])["auth_error"] == [reason]

    def test_reports_a_cancelled_consent_screen(self, no_redirects: TestClient):
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get(
            "/auth/google/callback", params={"error": "access_denied"}
        )

        self._assert_rejected(response, "access_denied")

    def test_rejects_a_callback_with_no_handshake_cookie(
        self, no_redirects: TestClient
    ):
        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        self._assert_rejected(response, "invalid_state")

    def test_rejects_a_state_that_does_not_match(self, no_redirects: TestClient):
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get(
            "/auth/google/callback",
            params={"code": "the-code", "state": "somebody-elses-state"},
        )

        self._assert_rejected(response, "invalid_state")

    def test_rejects_a_missing_state(self, no_redirects: TestClient):
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code"}
        )

        self._assert_rejected(response, "invalid_state")

    def test_rejects_a_forged_handshake_cookie(self, no_redirects: TestClient):
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, "not-a-jwt")

        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        self._assert_rejected(response, "invalid_state")

    def test_rejects_a_callback_with_no_code(self, no_redirects: TestClient):
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get("/auth/google/callback", params={"state": STATE})

        self._assert_rejected(response, "missing_code")

    def test_reports_a_token_google_will_not_stand_behind(
        self, no_redirects: TestClient, google
    ):
        google(raises=GoogleOAuthError("Google ID token failed verification"))
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        self._assert_rejected(response, "google_auth_failed")

    def test_a_failure_signs_nobody_in(
        self, no_redirects: TestClient, db: Session, google
    ):
        google(raises=GoogleOAuthError("nope"))
        no_redirects.cookies.set(OAUTH_STATE_COOKIE_NAME, state_cookie())

        response = no_redirects.get(
            "/auth/google/callback", params={"code": "the-code", "state": STATE}
        )

        assert ACCESS_TOKEN_COOKIE_NAME not in response.cookies
        assert user_count(db) == 0

    def test_a_failed_handshake_still_returns_to_the_frontend(
        self, no_redirects: TestClient
    ):
        response = no_redirects.get(
            "/auth/google/callback", params={"error": "access_denied"}
        )

        assert response.headers["location"].startswith(settings.frontend_url)


class TestIdTokenSignIn:
    def test_signs_the_user_in(self, client: TestClient, db: Session, google):
        google()

        response = client.post("/auth/google/token", json={"credential": "an.id.token"})

        assert response.status_code == 200
        assert response.json()["email"] == "someone@example.com"
        assert (
            decode_access_token(response.cookies[ACCESS_TOKEN_COOKIE_NAME])
            == db.scalars(select(User.id)).one()
        )

    def test_creates_the_user_and_the_linked_account(
        self, client: TestClient, db: Session, google
    ):
        google()

        client.post("/auth/google/token", json={"credential": "an.id.token"})

        db.expire_all()
        assert db.scalars(select(User)).one().hashed_password is None
        assert db.scalars(select(OAuthAccount)).one().provider == GOOGLE_PROVIDER

    def test_never_returns_the_password_hash(self, client: TestClient, google):
        google()

        response = client.post("/auth/google/token", json={"credential": "an.id.token"})

        assert "hashed_password" not in response.json()
        assert "password" not in response.json()

    def test_a_returning_google_user_is_not_duplicated(
        self, client: TestClient, db: Session, google
    ):
        google()

        for _ in range(2):
            client.post("/auth/google/token", json={"credential": "an.id.token"})

        assert user_count(db) == 1
        assert account_count(db) == 1

    def test_links_onto_a_local_account_with_the_same_email(
        self, client: TestClient, db: Session, google, make_user
    ):
        existing = make_user("someone@example.com", password="a-real-password")
        google()

        response = client.post("/auth/google/token", json={"credential": "an.id.token"})

        assert response.json()["id"] == str(existing.id)
        assert user_count(db) == 1

    def test_rejects_a_credential_google_will_not_stand_behind(
        self, client: TestClient, db: Session, google
    ):
        google(raises=GoogleOAuthError("Google ID token failed verification"))

        response = client.post("/auth/google/token", json={"credential": "nonsense"})

        assert response.status_code == 401
        assert user_count(db) == 0

    def test_rejects_a_payload_with_no_credential(self, client: TestClient):
        response = client.post("/auth/google/token", json={})

        assert response.status_code == 422

    def test_the_returned_cookie_authenticates(self, client: TestClient, google):
        google()

        client.post("/auth/google/token", json={"credential": "an.id.token"})

        assert client.get("/auth/me").status_code == 200


class TestSafeRedirectPath:
    @pytest.mark.parametrize("path", ["/", "/dashboard", "/a/b?c=d"])
    def test_keeps_a_plain_path(self, path):
        assert google_auth._safe_redirect_path(path) == path

    @pytest.mark.parametrize(
        "path",
        [
            "//evil.com",
            "/\\evil.com",
            "https://evil.com",
            "evil.com",
            "",
            None,
            123,
        ],
    )
    def test_falls_back_for_anything_offsite(self, path):
        assert google_auth._safe_redirect_path(path) == "/"

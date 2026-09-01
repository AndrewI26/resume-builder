from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from fastapi import Response

from config import get_settings
from services.security import (
    ACCESS_TOKEN_COOKIE_NAME,
    OAUTH_STATE_COOKIE_NAME,
    OAUTH_STATE_EXPIRE_MINUTES,
    create_access_token,
    create_oauth_state_token,
    decode_access_token,
    decode_oauth_state_token,
    hash_password,
    set_access_token_cookie,
    verify_password,
)

settings = get_settings()

OTHER_SECRET = "another-signing-key-that-is-long-enough"
PASSWORD = "correct-horse-battery"


def claims(token: str, *, secret: str | None = None) -> dict[str, Any]:
    return jwt.decode(
        token,
        secret or settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"verify_exp": False},
    )


def encode(
    payload: dict[str, Any], *, secret: str | None = None, algorithm: str = ""
) -> str:
    return jwt.encode(
        payload,
        secret or settings.secret_key,
        algorithm=algorithm or settings.jwt_algorithm,
    )


def cookie_header(response: Response) -> str:
    return response.headers["set-cookie"]


class TestPasswordHashing:
    """bcrypt is deliberately slow, so these stay few."""

    def test_a_password_verifies_against_its_own_hash(self):
        assert verify_password(PASSWORD, hash_password(PASSWORD)) is True

    def test_the_hash_is_not_the_password(self):
        hashed = hash_password(PASSWORD)

        assert PASSWORD not in hashed
        assert hashed.startswith("$2b$")

    def test_the_same_password_hashes_differently_each_time(self):
        """A per-hash salt: equal hashes would leak that two users share one."""
        assert hash_password(PASSWORD) != hash_password(PASSWORD)

    def test_rejects_the_wrong_password(self):
        assert verify_password("not-it", hash_password(PASSWORD)) is False

    def test_rejects_a_password_that_only_differs_in_case(self):
        assert verify_password(PASSWORD.upper(), hash_password(PASSWORD)) is False

    def test_handles_a_non_ascii_password(self):
        password = "pässwörd-ünïcode-🔐"

        assert verify_password(password, hash_password(password)) is True


class TestCreateAccessToken:
    def test_names_the_user_in_the_subject(self):
        user_id = uuid4()

        assert claims(create_access_token(user_id))["sub"] == str(user_id)

    def test_carries_an_expiry(self):
        assert "exp" in claims(create_access_token(uuid4()))

    def test_the_expiry_follows_the_configured_lifetime(self):
        expected = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

        expires_at = datetime.fromtimestamp(
            claims(create_access_token(uuid4()))["exp"], UTC
        )

        assert abs((expires_at - expected).total_seconds()) < 60

    def test_is_signed_with_the_server_key(self):
        token = create_access_token(uuid4())

        with pytest.raises(jwt.InvalidSignatureError):
            claims(token, secret=OTHER_SECRET)


class TestDecodeAccessToken:
    def test_round_trips_a_user_id(self):
        user_id = uuid4()

        assert decode_access_token(create_access_token(user_id)) == user_id

    def test_returns_none_for_a_malformed_token(self):
        assert decode_access_token("not-a-jwt") is None

    def test_returns_none_for_an_empty_token(self):
        assert decode_access_token("") is None

    def test_returns_none_for_another_signing_key(self):
        forged = encode(
            {"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
            secret=OTHER_SECRET,
        )

        assert decode_access_token(forged) is None

    def test_returns_none_for_an_expired_token(self):
        expired = encode(
            {"sub": str(uuid4()), "exp": datetime.now(UTC) - timedelta(seconds=1)}
        )

        assert decode_access_token(expired) is None

    def test_returns_none_when_there_is_no_subject(self):
        assert (
            decode_access_token(
                encode({"exp": datetime.now(UTC) + timedelta(minutes=5)})
            )
            is None
        )

    def test_returns_none_when_the_subject_is_not_a_uuid(self):
        token = encode(
            {"sub": "not-a-uuid", "exp": datetime.now(UTC) + timedelta(minutes=5)}
        )

        assert decode_access_token(token) is None

    def test_refuses_an_unsigned_token(self):
        """`alg: none` must not be accepted as a way past the signature."""
        unsigned = jwt.encode(
            {"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
            key="",
            algorithm="none",
        )

        assert decode_access_token(unsigned) is None


class TestSetAccessTokenCookie:
    def test_sets_a_token_that_decodes_back_to_the_user(self):
        response = Response()
        user_id = uuid4()

        set_access_token_cookie(response, user_id)

        value = cookie_header(response).split(";")[0].split("=", 1)[1]
        assert decode_access_token(value) == user_id

    def test_uses_the_expected_cookie_name(self):
        response = Response()

        set_access_token_cookie(response, uuid4())

        assert cookie_header(response).startswith(f"{ACCESS_TOKEN_COOKIE_NAME}=")

    def test_is_not_readable_from_javascript(self):
        response = Response()

        set_access_token_cookie(response, uuid4())

        assert "httponly" in cookie_header(response).lower()

    def test_is_sent_on_top_level_navigations_only(self):
        response = Response()

        set_access_token_cookie(response, uuid4())

        assert "samesite=lax" in cookie_header(response).lower()

    def test_expires_with_the_token(self):
        response = Response()

        set_access_token_cookie(response, uuid4())

        max_age = settings.access_token_expire_minutes * 60
        assert f"max-age={max_age}" in cookie_header(response).lower()

    def test_the_secure_flag_follows_the_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "node_env", "production")
        response = Response()

        set_access_token_cookie(response, uuid4())

        assert "secure" in cookie_header(response).lower()

    def test_stays_insecure_for_local_http(self, monkeypatch):
        monkeypatch.setattr(settings, "node_env", "development")
        response = Response()

        set_access_token_cookie(response, uuid4())

        assert "secure" not in cookie_header(response).lower()


class TestOAuthStateToken:
    def test_round_trips_the_handshake_claims(self):
        handshake = {"state": "s", "nonce": "n", "code_verifier": "v", "next": "/here"}

        decoded = decode_oauth_state_token(create_oauth_state_token(handshake))

        assert decoded is not None
        assert {key: decoded[key] for key in handshake} == handshake

    def test_carries_its_own_short_expiry(self):
        expected = datetime.now(UTC) + timedelta(minutes=OAUTH_STATE_EXPIRE_MINUTES)

        decoded = decode_oauth_state_token(create_oauth_state_token({}))

        assert decoded is not None
        expires_at = datetime.fromtimestamp(decoded["exp"], UTC)
        assert abs((expires_at - expected).total_seconds()) < 60

    def test_is_shorter_lived_than_a_session(self):
        assert OAUTH_STATE_EXPIRE_MINUTES < settings.access_token_expire_minutes

    def test_returns_none_for_a_malformed_token(self):
        assert decode_oauth_state_token("not-a-jwt") is None

    def test_returns_none_for_another_signing_key(self):
        forged = encode(
            {"state": "s", "exp": datetime.now(UTC) + timedelta(minutes=5)},
            secret=OTHER_SECRET,
        )

        assert decode_oauth_state_token(forged) is None

    def test_returns_none_once_expired(self):
        expired = encode(
            {"state": "s", "exp": datetime.now(UTC) - timedelta(seconds=1)}
        )

        assert decode_oauth_state_token(expired) is None

    def test_a_tampered_payload_is_rejected(self):
        token = create_oauth_state_token({"state": "mine", "next": "/"})
        header, _payload, signature = token.split(".")
        other = create_oauth_state_token({"state": "theirs", "next": "/"})

        spliced = f"{header}.{other.split('.')[1]}.{signature}"

        assert decode_oauth_state_token(spliced) is None

    def test_the_two_token_kinds_have_different_names(self):
        assert ACCESS_TOKEN_COOKIE_NAME != OAUTH_STATE_COOKIE_NAME

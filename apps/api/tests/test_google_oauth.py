"""The Google OAuth helpers.

Google's signing keys are the one thing that can't be exercised for real, so a
throwaway RSA key stands in for them: tokens here are genuinely signed and
genuinely verified, and only the JWKS lookup is replaced.
"""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from services import google_oauth
from services.google_oauth import (
    AUTHORIZATION_ENDPOINT,
    ISSUERS,
    SCOPES,
    TOKEN_ENDPOINT,
    GoogleOAuthError,
    build_authorization_url,
    exchange_code_for_id_token,
    generate_pkce_pair,
    verify_id_token,
)
from settings import get_settings

settings = get_settings()

CLIENT_ID = "client-id.apps.googleusercontent.com"
CLIENT_SECRET = "client-secret"
NONCE = "the-nonce"

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeSigningKey:
    def __init__(self, key) -> None:
        self.key = key


class FakeJwksClient:
    """Stands in for Google's JWKS endpoint."""

    def __init__(self, key, raises: Exception | None = None) -> None:
        self._key = key
        self._raises = raises

    def get_signing_key_from_jwt(self, token):
        if self._raises is not None:
            raise self._raises
        return FakeSigningKey(self._key.public_key())


class FakeResponse:
    def __init__(self, status_code: int, payload) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def id_token(*, key=SIGNING_KEY, **overrides) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-1",
        "email": "someone@example.com",
        "email_verified": True,
        "name": "Someone",
        "nonce": NONCE,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    claims.update(overrides)
    # `...` in an override means "Google omitted this claim entirely"
    present = {name: value for name, value in claims.items() if value is not ...}
    return jwt.encode(present, key, algorithm="RS256")


def query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """Every test here assumes a server with Google credentials set."""
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_client_secret", CLIENT_SECRET)


@pytest.fixture
def google_keys(monkeypatch):
    monkeypatch.setattr(google_oauth, "_jwks_client", FakeJwksClient(SIGNING_KEY))


@pytest.fixture
def post(monkeypatch):
    """Capture the token-endpoint call and choose what Google answers."""
    calls: list[dict] = []

    def _post(*, status_code: int = 200, payload=None, raises: Exception | None = None):
        def _fake_post(url, data=None, timeout=None):
            calls.append({"url": url, "data": data, "timeout": timeout})
            if raises is not None:
                raise raises
            return FakeResponse(status_code, payload)

        monkeypatch.setattr(google_oauth.httpx, "post", _fake_post)
        return calls

    return _post


class TestGeneratePkcePair:
    def test_returns_a_verifier_and_a_challenge(self):
        verifier, challenge = generate_pkce_pair()

        assert verifier and challenge
        assert verifier != challenge

    def test_is_different_every_time(self):
        assert generate_pkce_pair()[0] != generate_pkce_pair()[0]

    def test_the_challenge_is_the_sha256_of_the_verifier(self):
        verifier, challenge = generate_pkce_pair()

        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        assert challenge == base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def test_the_challenge_is_unpadded_and_url_safe(self):
        _, challenge = generate_pkce_pair()

        assert "=" not in challenge
        assert "+" not in challenge and "/" not in challenge

    def test_the_verifier_is_long_enough_to_be_unguessable(self):
        verifier, _ = generate_pkce_pair()

        assert len(verifier) >= 43  # the RFC 7636 minimum


class TestBuildAuthorizationUrl:
    def url(self, **overrides) -> str:
        params = {
            "state": "the-state",
            "nonce": NONCE,
            "code_challenge": "the-challenge",
        }
        params.update(overrides)
        return build_authorization_url(**params)

    def test_points_at_googles_consent_screen(self):
        assert self.url().startswith(f"{AUTHORIZATION_ENDPOINT}?")

    def test_identifies_this_client(self):
        assert query(self.url())["client_id"] == [CLIENT_ID]

    def test_asks_for_an_authorization_code(self):
        assert query(self.url())["response_type"] == ["code"]

    def test_asks_for_the_identity_scopes(self):
        assert query(self.url())["scope"] == [" ".join(SCOPES)]

    def test_passes_the_state_and_nonce_through(self):
        params = query(self.url())

        assert params["state"] == ["the-state"]
        assert params["nonce"] == [NONCE]

    def test_binds_the_request_with_pkce(self):
        params = query(self.url())

        assert params["code_challenge"] == ["the-challenge"]
        assert params["code_challenge_method"] == ["S256"]

    def test_sends_the_registered_redirect_uri(self):
        assert query(self.url())["redirect_uri"] == [settings.google_redirect_uri]

    def test_does_not_ask_for_a_refresh_token(self):
        """We only need identity, so there is no long lived token to leak."""
        assert query(self.url())["access_type"] == ["online"]

    def test_lets_the_user_pick_an_account(self):
        assert query(self.url())["prompt"] == ["select_account"]

    def test_escapes_values_into_the_query_string(self):
        assert query(self.url(state="a b&c=d"))["state"] == ["a b&c=d"]

    def test_refuses_when_the_client_id_is_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "google_client_id", None)

        with pytest.raises(GoogleOAuthError, match="GOOGLE_CLIENT_ID"):
            self.url()


class TestExchangeCodeForIdToken:
    def test_returns_the_id_token(self, post):
        post(payload={"id_token": "an.id.token"})

        assert exchange_code_for_id_token("the-code", "the-verifier") == "an.id.token"

    def test_calls_googles_token_endpoint(self, post):
        calls = post(payload={"id_token": "an.id.token"})

        exchange_code_for_id_token("the-code", "the-verifier")

        assert calls[0]["url"] == TOKEN_ENDPOINT

    def test_sends_the_code_and_the_pkce_verifier(self, post):
        calls = post(payload={"id_token": "an.id.token"})

        exchange_code_for_id_token("the-code", "the-verifier")

        assert calls[0]["data"]["code"] == "the-code"
        assert calls[0]["data"]["code_verifier"] == "the-verifier"
        assert calls[0]["data"]["grant_type"] == "authorization_code"

    def test_authenticates_as_this_client(self, post):
        calls = post(payload={"id_token": "an.id.token"})

        exchange_code_for_id_token("the-code", "the-verifier")

        assert calls[0]["data"]["client_id"] == CLIENT_ID
        assert calls[0]["data"]["client_secret"] == CLIENT_SECRET
        assert calls[0]["data"]["redirect_uri"] == settings.google_redirect_uri

    def test_does_not_hang_forever(self, post):
        calls = post(payload={"id_token": "an.id.token"})

        exchange_code_for_id_token("the-code", "the-verifier")

        assert calls[0]["timeout"] is not None

    def test_raises_when_google_rejects_the_code(self, post):
        post(status_code=400, payload={"error": "invalid_grant"})

        with pytest.raises(GoogleOAuthError, match="rejected the authorization code"):
            exchange_code_for_id_token("stale-code", "the-verifier")

    def test_the_error_does_not_leak_googles_response_body(self, post):
        post(status_code=400, payload={"error": "invalid_grant"})

        with pytest.raises(GoogleOAuthError) as exc_info:
            exchange_code_for_id_token("stale-code", "the-verifier")

        assert "invalid_grant" not in str(exc_info.value)

    def test_raises_when_the_response_carries_no_id_token(self, post):
        post(payload={"access_token": "not-what-we-asked-for"})

        with pytest.raises(GoogleOAuthError, match="no id_token"):
            exchange_code_for_id_token("the-code", "the-verifier")

    def test_raises_when_the_id_token_is_not_a_string(self, post):
        post(payload={"id_token": {"unexpected": "shape"}})

        with pytest.raises(GoogleOAuthError, match="no id_token"):
            exchange_code_for_id_token("the-code", "the-verifier")

    def test_raises_when_google_cannot_be_reached(self, post):
        post(raises=httpx.ConnectError("no route to host"))

        with pytest.raises(GoogleOAuthError, match="Could not reach Google"):
            exchange_code_for_id_token("the-code", "the-verifier")

    def test_raises_when_it_times_out(self, post):
        post(raises=httpx.ReadTimeout("too slow"))

        with pytest.raises(GoogleOAuthError, match="Could not reach Google"):
            exchange_code_for_id_token("the-code", "the-verifier")

    def test_refuses_when_the_client_secret_is_missing(self, post, monkeypatch):
        post(payload={"id_token": "an.id.token"})
        monkeypatch.setattr(settings, "google_client_secret", None)

        with pytest.raises(GoogleOAuthError, match="GOOGLE_CLIENT_SECRET"):
            exchange_code_for_id_token("the-code", "the-verifier")


@pytest.mark.usefixtures("google_keys")
class TestVerifyIdToken:
    def test_returns_the_profile_behind_a_good_token(self):
        profile = verify_id_token(id_token())

        assert profile.sub == "google-sub-1"
        assert profile.email == "someone@example.com"
        assert profile.email_verified is True
        assert profile.name == "Someone"

    def test_accepts_either_spelling_of_the_issuer(self):
        for issuer in ISSUERS:
            assert verify_id_token(id_token(iss=issuer)).sub == "google-sub-1"

    def test_lowercases_the_email(self):
        assert verify_id_token(id_token(email="Someone@Example.COM")).email == (
            "someone@example.com"
        )

    def test_trims_the_display_name(self):
        assert verify_id_token(id_token(name="  Someone  ")).name == "Someone"

    def test_has_no_name_when_google_omits_one(self):
        assert verify_id_token(id_token(name=...)).name is None

    def test_has_no_name_when_google_sends_a_blank_one(self):
        assert verify_id_token(id_token(name="   ")).name is None

    def test_rejects_a_token_signed_by_someone_else(self):
        with pytest.raises(GoogleOAuthError, match="failed verification"):
            verify_id_token(id_token(key=OTHER_KEY))

    def test_rejects_a_token_minted_for_another_client(self):
        with pytest.raises(GoogleOAuthError, match="failed verification"):
            verify_id_token(id_token(aud="somebody-elses-client-id"))

    def test_rejects_an_expired_token(self):
        stale = id_token(exp=datetime.now(UTC) - timedelta(seconds=1))

        with pytest.raises(GoogleOAuthError, match="failed verification"):
            verify_id_token(stale)

    def test_rejects_an_unexpected_issuer(self):
        with pytest.raises(GoogleOAuthError, match="unexpected issuer"):
            verify_id_token(id_token(iss="https://evil.example.com"))

    def test_rejects_a_garbage_token(self):
        with pytest.raises(GoogleOAuthError, match="failed verification"):
            verify_id_token("not-a-jwt")

    @pytest.mark.parametrize("claim", ["sub", "exp", "iat", "aud", "iss"])
    def test_requires_the_claims_it_relies_on(self, claim):
        with pytest.raises(GoogleOAuthError):
            verify_id_token(id_token(**{claim: ...}))

    def test_rejects_an_unverified_email(self):
        """Linking by email is only safe because this check exists."""
        with pytest.raises(GoogleOAuthError, match="not verified"):
            verify_id_token(id_token(email_verified=False))

    def test_rejects_a_missing_email_verified_claim(self):
        with pytest.raises(GoogleOAuthError, match="not verified"):
            verify_id_token(id_token(email_verified=...))

    def test_rejects_a_stringly_typed_email_verified(self):
        with pytest.raises(GoogleOAuthError, match="not verified"):
            verify_id_token(id_token(email_verified="true"))

    def test_rejects_a_token_with_no_email(self):
        with pytest.raises(GoogleOAuthError, match="did not share an email"):
            verify_id_token(id_token(email=...))

    def test_rejects_an_empty_email(self):
        with pytest.raises(GoogleOAuthError, match="did not share an email"):
            verify_id_token(id_token(email=""))

    def test_checks_the_nonce_when_one_is_expected(self):
        assert verify_id_token(id_token(), expected_nonce=NONCE).sub == "google-sub-1"

    def test_rejects_a_replayed_nonce(self):
        with pytest.raises(GoogleOAuthError, match="nonce did not match"):
            verify_id_token(
                id_token(nonce="somebody-elses-nonce"), expected_nonce=NONCE
            )

    def test_rejects_a_missing_nonce_when_one_is_expected(self):
        with pytest.raises(GoogleOAuthError, match="nonce did not match"):
            verify_id_token(id_token(nonce=...), expected_nonce=NONCE)

    def test_ignores_the_nonce_when_none_is_expected(self):
        """Tokens from the sign in button carry a nonce we never chose."""
        assert verify_id_token(id_token(nonce="not-ours")).sub == "google-sub-1"

    def test_refuses_when_the_client_id_is_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "google_client_id", None)

        with pytest.raises(GoogleOAuthError, match="GOOGLE_CLIENT_ID"):
            verify_id_token(id_token())

    def test_raises_when_googles_keys_cannot_be_fetched(self, monkeypatch):
        monkeypatch.setattr(
            google_oauth,
            "_jwks_client",
            FakeJwksClient(SIGNING_KEY, raises=jwt.PyJWKClientError("jwks is down")),
        )

        with pytest.raises(GoogleOAuthError, match="failed verification"):
            verify_id_token(id_token())

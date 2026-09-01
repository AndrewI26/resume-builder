"""Google OAuth 2.0 / OpenID Connect helpers.

Covers both ways a frontend can sign a user in with Google:

* the redirect (authorization code) flow, via `build_authorization_url` +
  `exchange_code_for_id_token`
* the Google Identity Services button, which hands the frontend an ID token
  directly and only needs `verify_id_token`

Both funnel into `verify_id_token`, which is the only thing that decides who
the caller actually is.
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from config import get_settings

settings = get_settings()

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")

SCOPES = ("openid", "email", "profile")

# caches Google's signing keys in memory so we aren't fetching JWKS per login
_jwks_client = jwt.PyJWKClient(JWKS_URI, cache_keys=True)

_HTTP_TIMEOUT = httpx.Timeout(10.0)


class GoogleOAuthError(Exception):
    """Raised when Google rejects us or returns something we can't trust."""


@dataclass(frozen=True)
class GoogleProfile:
    """The subset of verified ID token claims we care about."""

    sub: str
    email: str
    email_verified: bool
    name: str | None = None


def generate_pkce_pair() -> tuple[str, str]:
    """Return an (code_verifier, code_challenge) pair for PKCE (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorization_url(*, state: str, nonce: str, code_challenge: str) -> str:
    params = {
        "client_id": _require_client_id(),
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        # we only need identity, so no refresh token to store or leak
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_id_token(code: str, code_verifier: str) -> str:
    """Trade an authorization code for the ID token identifying the user."""
    data = {
        "code": code,
        "client_id": _require_client_id(),
        "client_secret": _require_client_secret(),
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }

    try:
        response = httpx.post(TOKEN_ENDPOINT, data=data, timeout=_HTTP_TIMEOUT)
    except httpx.HTTPError as exc:
        raise GoogleOAuthError("Could not reach Google to exchange the code") from exc

    if response.status_code != HTTPStatus.OK:
        raise GoogleOAuthError(
            f"Google rejected the authorization code ({response.status_code})"
        )

    id_token = response.json().get("id_token")
    if not isinstance(id_token, str):
        raise GoogleOAuthError("Google's token response contained no id_token")

    return id_token


def verify_id_token(
    id_token: str, *, expected_nonce: str | None = None
) -> GoogleProfile:
    """Verify a Google ID token's signature and claims, or raise.

    `expected_nonce` is checked for the redirect flow, where we chose the nonce
    ourselves. Tokens minted for the Google Identity Services button carry a
    nonce we never saw, so callers there pass None.
    """
    client_id = _require_client_id()

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(id_token)
        claims: dict[str, Any] = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        raise GoogleOAuthError("Google ID token failed verification") from exc

    if claims.get("iss") not in ISSUERS:
        raise GoogleOAuthError("Google ID token has an unexpected issuer")

    if expected_nonce is not None and claims.get("nonce") != expected_nonce:
        raise GoogleOAuthError("Google ID token nonce did not match")

    email = claims.get("email")
    if not email:
        raise GoogleOAuthError("Google account did not share an email address")

    # an unverified email would let anyone claim someone else's account when we
    # link a Google identity to an existing local user by email
    if claims.get("email_verified") is not True:
        raise GoogleOAuthError("Google account email is not verified")

    # `name` rides on the "profile" scope and is best effort: Google omits it
    # for accounts that haven't set one
    name = claims.get("name")

    return GoogleProfile(
        sub=str(claims["sub"]),
        email=str(email).lower(),
        email_verified=True,
        name=str(name).strip() or None if name else None,
    )


def _require_client_id() -> str:
    if not settings.google_client_id:
        raise GoogleOAuthError("GOOGLE_CLIENT_ID is not configured")
    return settings.google_client_id


def _require_client_secret() -> str:
    if not settings.google_client_secret:
        raise GoogleOAuthError("GOOGLE_CLIENT_SECRET is not configured")
    return settings.google_client_secret

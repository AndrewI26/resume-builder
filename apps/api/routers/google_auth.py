"""Sign in with Google.

Two entry points, so the frontend can pick whichever it prefers:

* redirect flow — send the browser to `GET /auth/google/login`; we bounce it to
  Google and Google bounces it back to `GET /auth/google/callback`, which sets
  the session cookie and redirects into the app.
* ID token flow — render Google's own button, then POST the credential it
  yields to `POST /auth/google/token`.

Either way the user ends up with the same `access_token` cookie that
`/auth/login` issues, so the rest of the API is unchanged.
"""

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from deps.db import Db
from google_oauth import (
    GoogleOAuthError,
    GoogleProfile,
    build_authorization_url,
    exchange_code_for_id_token,
    generate_pkce_pair,
    verify_id_token,
)
from models.oauth_account import GOOGLE_PROVIDER, OAuthAccount
from models.user import User
from schemas.user import GoogleCredential, UserRead
from security import (
    OAUTH_STATE_COOKIE_NAME,
    OAUTH_STATE_EXPIRE_MINUTES,
    create_oauth_state_token,
    decode_oauth_state_token,
    set_access_token_cookie,
)
from settings import get_settings

router = APIRouter(prefix="/auth/google", tags=["Auth"])

settings = get_settings()

# the state cookie is only ever read back by the callback below
STATE_COOKIE_PATH = "/auth/google"

DEFAULT_REDIRECT_PATH = "/"


@router.get(
    "/login",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    summary="Start the Google sign in redirect flow",
)
def login(next: str = DEFAULT_REDIRECT_PATH) -> RedirectResponse:
    """Redirect the browser to Google's consent screen.

    `next` is a path inside the frontend to land on afterwards, e.g.
    `/auth/google/login?next=/dashboard`.
    """
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign in is not configured on this server",
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()

    try:
        authorization_url = build_authorization_url(
            state=state, nonce=nonce, code_challenge=code_challenge
        )
    except GoogleOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    response = RedirectResponse(
        authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=create_oauth_state_token(
            {
                "state": state,
                "nonce": nonce,
                "code_verifier": code_verifier,
                "next": _safe_redirect_path(next),
            }
        ),
        httponly=True,
        secure=settings.cookie_secure,
        # "lax" still sends the cookie on Google's top level redirect back to us
        samesite="lax",
        max_age=OAUTH_STATE_EXPIRE_MINUTES * 60,
        path=STATE_COOKIE_PATH,
    )
    return response


@router.get(
    "/callback",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    summary="Google redirects here after the user consents",
)
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Db,
    oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE_NAME),
) -> RedirectResponse:
    """Complete the handshake, set the session cookie, return to the frontend.

    This is a browser navigation rather than an API call, so failures redirect
    back to the frontend with an `auth_error` query param instead of returning
    a JSON error the user would see as a raw page.
    """

    def _finish(
        path: str = DEFAULT_REDIRECT_PATH, auth_error: str | None = None
    ) -> RedirectResponse:
        """Redirect back to the frontend, retiring the handshake cookie."""
        response = _frontend_redirect(path, auth_error=auth_error)
        response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=STATE_COOKIE_PATH)
        return response

    stored = decode_oauth_state_token(oauth_state) if oauth_state else None

    # the redirect target was chosen before the handshake started; fall back to
    # the default if we can't read it back
    next_path = DEFAULT_REDIRECT_PATH
    if stored is not None:
        next_path = _safe_redirect_path(stored.get("next"))

    if error is not None:
        # the user hit "cancel" on Google's consent screen, most likely
        return _finish(auth_error=error)

    state_matches = (
        stored is not None
        and bool(state)
        and secrets.compare_digest(str(stored.get("state", "")), str(state))
    )
    if stored is None or not state_matches:
        return _finish(auth_error="invalid_state")

    if not code:
        return _finish(auth_error="missing_code")

    try:
        id_token = exchange_code_for_id_token(code, str(stored["code_verifier"]))
        profile = verify_id_token(id_token, expected_nonce=str(stored["nonce"]))
    except GoogleOAuthError:
        return _finish(auth_error="google_auth_failed")

    user = _get_or_create_user(db, profile)

    response = _finish(next_path)
    set_access_token_cookie(response, user.id)
    return response


@router.post(
    "/token",
    response_model=UserRead,
    summary="Sign in with an ID token from Google Identity Services",
)
def token(payload: GoogleCredential, response: Response, db: Session = Db) -> User:
    """Exchange the `credential` from Google's sign in button for a session."""
    try:
        # no nonce check: this token was minted for the frontend, not for us
        profile = verify_id_token(payload.credential)
    except GoogleOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    user = _get_or_create_user(db, profile)
    set_access_token_cookie(response, user.id)
    return user


def _get_or_create_user(db: Session, profile: GoogleProfile) -> User:
    """Find the user behind a verified Google profile, creating one if new.

    A Google identity we've seen before wins outright. Otherwise we link to the
    local account with the same email if there is one — safe only because
    `verify_id_token` refuses unverified emails — and create a passwordless
    user if there isn't.
    """
    account = _find_account(db, profile.sub)

    if account is None:
        user = db.query(User).filter(func.lower(User.email) == profile.email).first()
        if user is None:
            user = User(email=profile.email, name=profile.name, hashed_password=None)
            db.add(user)
            db.flush()
        else:
            _backfill_name(user, profile)

        account = OAuthAccount(
            user_id=user.id,
            provider=GOOGLE_PROVIDER,
            provider_account_id=profile.sub,
            email=profile.email,
        )
        db.add(account)

        try:
            db.commit()
        except IntegrityError:
            # two sign ins raced to create the same account; the other one won
            db.rollback()
            account = _find_account(db, profile.sub)
            if account is None:
                raise

        return account.user if account is not None else user

    if account.email != profile.email:
        account.email = profile.email

    _backfill_name(account.user, profile)
    db.commit()

    return account.user


def _backfill_name(user: User, profile: GoogleProfile) -> None:
    """Fill in a missing display name from Google.

    Only ever fills a blank: once the user can edit their own name we mustn't
    overwrite it with whatever Google has on every sign in.
    """
    if user.name is None and profile.name is not None:
        user.name = profile.name


def _find_account(db: Session, google_sub: str) -> OAuthAccount | None:
    return (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_account_id == google_sub,
        )
        .first()
    )


def _safe_redirect_path(path: object) -> str:
    """Keep post-login redirects on the frontend origin.

    Anything that isn't a plain absolute path (`//evil.com`, `https://…`) would
    turn this endpoint into an open redirect, so it falls back to the default.
    """
    if not isinstance(path, str) or not path.startswith("/"):
        return DEFAULT_REDIRECT_PATH
    # a leading "//" or "/\" is read as a protocol relative URL by browsers
    if path.startswith(("//", "/\\")):
        return DEFAULT_REDIRECT_PATH
    return path


def _frontend_redirect(path: str, auth_error: str | None = None) -> RedirectResponse:
    url = f"{settings.frontend_url.rstrip('/')}{path}"
    if auth_error is not None:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode({'auth_error': auth_error})}"
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)

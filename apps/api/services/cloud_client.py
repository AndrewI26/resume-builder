"""Talking to the hosted API from a desktop install.

The only place this application makes an outbound request. It exists because
the account is somewhere else; everything else the desktop does is local by
construction.

Failures here are ordinary and expected — a laptop is offline more often than a
server is — so they are turned into one exception the caller can report as "not
now" rather than a stack trace about sockets.
"""

from typing import Any, Self

import httpx

from services.security import ACCESS_TOKEN_COOKIE_NAME

#: Long enough for a large first sync, short enough that a dead network is not
#: mistaken for a slow one.
TIMEOUT_SECONDS = 30.0


class CloudUnreachable(Exception):
    """The account could not be reached, or refused to answer."""


class CloudRejectedCredentials(Exception):
    """The email and password were not accepted."""


def sign_in(base_url: str, email: str, password: str) -> tuple[str, str]:
    """Exchange an email and password for a session. Returns (token, email)."""
    try:
        with httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS) as client:
            response = client.post(
                "/auth/login", json={"email": email, "password": password}
            )
    except httpx.HTTPError as error:
        raise CloudUnreachable(str(error)) from error

    if response.status_code == 401:
        raise CloudRejectedCredentials("that email and password were not accepted")
    if response.status_code >= 400:
        raise CloudUnreachable(f"the account answered {response.status_code}")

    token = response.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if token is None:
        raise CloudUnreachable("the account did not return a session")

    return token, str(response.json().get("email", email))


class CloudApi:
    """The account, reached over the network. Satisfies ``sync_engine.Cloud``."""

    def __init__(self, base_url: str, token: str) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=TIMEOUT_SECONDS,
            cookies={ACCESS_TOKEN_COOKIE_NAME: token},
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    def _json(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 401:
            raise CloudRejectedCredentials("this session is no longer valid")
        if response.status_code >= 400:
            raise CloudUnreachable(f"the account answered {response.status_code}")

        return dict(response.json())

    def pull(self, since: int, limit: int) -> dict[str, Any]:
        try:
            response = self._client.get(
                "/sync/changes", params={"since": since, "limit": limit}
            )
        except httpx.HTTPError as error:
            raise CloudUnreachable(str(error)) from error

        return self._json(response)

    def push(self, changes: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = self._client.post("/sync/push", json={"changes": changes})
        except httpx.HTTPError as error:
            raise CloudUnreachable(str(error)) from error

        return self._json(response)

"""Keeping the local API to the app that started it.

The desktop sidecar listens on loopback. That keeps it off the network, but
loopback is not private on the machine itself: any other program running as the
same person can connect to it, and this one answers every question about their
library without asking who is calling, because in local mode there is nothing
to sign in to.

So the shell generates a secret when it starts the sidecar, gives it to nobody
but its own renderer, and the sidecar refuses anything that does not carry it.
The port being unpredictable is not protection — anything can scan loopback —
and the secret is what actually distinguishes the app's own window from
whatever else the person happens to be running.

Only applied when a token was supplied, so running local mode by hand for
development stays as convenient as it was.
"""

from collections.abc import Awaitable, Callable
from secrets import compare_digest

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

TOKEN_HEADER = "x-sidecar-token"


def sidecar_token_guard(
    expected: str,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Middleware refusing any request that does not carry ``expected``."""

    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # A preflight cannot carry the header — asking permission to send it is
        # the entire point of the request — and it reveals nothing, so it is
        # answered by the CORS layer below without a token.
        if request.method == "OPTIONS":
            return await call_next(request)

        supplied = request.headers.get(TOKEN_HEADER)
        # compare_digest rather than ==: a timing difference here is a slow but
        # real way to learn the secret one byte at a time
        if supplied is None or not compare_digest(supplied, expected):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "This API only answers the app that started it"},
            )

        return await call_next(request)

    return guard

"""Handing LaTeX to the compile service.

The service is a separate container reachable only on the internal network.
It knows nothing about users or resumes; it takes source and returns a PDF,
which is what keeps it small enough to trust with a document it did not write.
"""

from functools import lru_cache

import httpx

from settings import get_settings


class CompilerError(Exception):
    """The base for anything that went wrong producing a PDF."""


class DocumentRejected(CompilerError):
    """The engine could not typeset the source. The caller's document is at fault."""

    def __init__(self, log: str):
        super().__init__("the document failed to compile")
        self.log = log


class CompilerUnavailable(CompilerError):
    """The service is unreachable, overloaded, or misconfigured."""


@lru_cache
def _client() -> httpx.Client:
    """One pooled client for the process, built on first use.

    The read timeout has to clear the compiler's own limit, otherwise this side
    gives up first and the engine is left running with nobody waiting for it.
    """
    return httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0))


def compile_to_pdf(source: str) -> bytes:
    settings = get_settings()

    if not settings.compiler_token:
        raise CompilerUnavailable("COMPILER_TOKEN is not configured")

    try:
        response = _client().post(
            f"{settings.compiler_url.rstrip('/')}/compile",
            content=source.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.compiler_token}",
                "Content-Type": "application/x-tex; charset=utf-8",
            },
        )
    except httpx.HTTPError as error:
        raise CompilerUnavailable(str(error)) from error

    if response.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
        raise DocumentRejected(response.text)

    if response.status_code != httpx.codes.OK:
        raise CompilerUnavailable(
            f"compiler returned {response.status_code}: {response.text[:200]}"
        )

    return response.content

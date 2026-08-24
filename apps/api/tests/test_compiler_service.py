"""The client for the LaTeX compile service, against a stubbed transport.

The sandboxing that makes it safe to hand the service a document someone else
wrote lives in the service itself and is tested there, in Go. These cover the
API's side of the conversation: what it sends, and how it classifies what
comes back.
"""

import httpx
import pytest

from services import compiler
from services.compiler import CompilerUnavailable, DocumentRejected

SOURCE = r"\documentclass{article}\begin{document}Hi\end{document}"
PDF = b"%PDF-1.5\nfake\n"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    settings = compiler.get_settings()
    monkeypatch.setattr(settings, "compiler_token", "a-token", raising=False)
    monkeypatch.setattr(settings, "compiler_port", 8100, raising=False)
    # Clearing on the way in is enough: monkeypatch restores the real
    # `_client` after this fixture tears down, so clearing on the way out
    # would run against a stub and find no cache to clear.
    compiler._client.cache_clear()
    yield


def stub(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(compiler, "_client", lambda: httpx.Client(transport=transport))


def test_sends_the_source_with_the_shared_token(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.content
        seen["url"] = str(request.url)
        return httpx.Response(200, content=PDF)

    stub(monkeypatch, handler)

    assert compiler.compile_to_pdf(SOURCE) == PDF
    assert seen["auth"] == "Bearer a-token"
    assert seen["body"] == SOURCE.encode()
    assert seen["url"] == "http://localhost:8100/compile"


def test_turns_a_422_into_a_rejected_document(monkeypatch):
    stub(monkeypatch, lambda request: httpx.Response(422, text="! Missing $ inserted."))

    with pytest.raises(DocumentRejected) as caught:
        compiler.compile_to_pdf(SOURCE)

    assert "Missing $" in caught.value.log


def test_turns_a_503_into_unavailable(monkeypatch):
    stub(monkeypatch, lambda request: httpx.Response(503, text="busy"))

    with pytest.raises(CompilerUnavailable):
        compiler.compile_to_pdf(SOURCE)


def test_turns_a_transport_error_into_unavailable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    stub(monkeypatch, handler)

    with pytest.raises(CompilerUnavailable):
        compiler.compile_to_pdf(SOURCE)


def test_refuses_to_run_without_a_token(monkeypatch):
    """PDF export is off rather than attempted when the token is unset."""
    settings = compiler.get_settings()
    monkeypatch.setattr(settings, "compiler_token", None, raising=False)

    with pytest.raises(CompilerUnavailable):
        compiler.compile_to_pdf(SOURCE)

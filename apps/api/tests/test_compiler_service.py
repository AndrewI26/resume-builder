"""The client for the LaTeX compile service, against a stubbed transport.

The sandboxing that makes it safe to hand the service a document someone else
wrote lives in the service itself and is tested there, in Go. These cover the
API's side of the conversation: what it sends, and how it classifies what
comes back.
"""

from typing import Any
from uuid import uuid4

import httpx
import pytest

from services import compiler
from services.compiler import CompilerUnavailable, DocumentRejected
from settings import get_settings

SOURCE = r"\documentclass{article}\begin{document}Hi\end{document}"
PDF = b"%PDF-1.5\nfake\n"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    settings = get_settings()
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
    seen: dict[str, Any] = {}

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
    settings = get_settings()
    monkeypatch.setattr(settings, "compiler_token", None, raising=False)

    with pytest.raises(CompilerUnavailable):
        compiler.compile_to_pdf(SOURCE)


class TestPdfEndpoint:
    """The endpoint's own behaviour: authorization, and how it translates the
    compile service's answers. The sandboxing is tested in Go."""

    @pytest.fixture
    def compiles(self, monkeypatch):
        calls = []

        def _compile(source: str) -> bytes:
            calls.append(source)
            return PDF

        monkeypatch.setattr("routers.resume.compile_to_pdf", _compile)
        return calls

    def test_requires_a_session_cookie(self, client):
        response = client.post(f"/resumes/{uuid4()}/pdf", json={"source": SOURCE})

        assert response.status_code == 401

    def test_hides_another_users_resume(
        self, auth, user, other_user, make_resume, compiles
    ):
        resume = make_resume(other_user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf", json={"source": SOURCE})

        assert response.status_code == 404
        assert compiles == [], "compiled a resume the caller does not own"

    def test_returns_the_pdf(self, auth, user, make_resume, compiles):
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf", json={"source": SOURCE})

        assert response.status_code == 200
        assert response.content == PDF
        assert response.headers["content-type"] == "application/pdf"
        assert compiles == [SOURCE]

    def test_names_the_download_after_the_resume(
        self, auth, user, make_resume, compiles
    ):
        resume = make_resume(user, title="Backend Engineer")

        response = auth(user).post(f"/resumes/{resume.id}/pdf", json={"source": SOURCE})

        assert (
            'filename="backend-engineer.pdf"'
            in (response.headers["content-disposition"])
        )

    def test_rejects_an_oversized_source(self, auth, user, make_resume, compiles):
        resume = make_resume(user)

        response = auth(user).post(
            f"/resumes/{resume.id}/pdf", json={"source": "x" * 1_000_001}
        )

        assert response.status_code == 422
        assert compiles == []

    def test_a_bad_document_comes_back_with_the_log(
        self, auth, user, make_resume, monkeypatch
    ):
        def _compile(source: str) -> bytes:
            raise DocumentRejected("! Undefined control sequence.")

        monkeypatch.setattr("routers.resume.compile_to_pdf", _compile)
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf", json={"source": SOURCE})

        assert response.status_code == 422
        assert "Undefined control sequence" in response.json()["detail"]

    def test_an_unreachable_compiler_does_not_leak_its_message(
        self, auth, user, make_resume, monkeypatch
    ):
        def _compile(source: str) -> bytes:
            raise CompilerUnavailable("connection refused to compiler:8100")

        monkeypatch.setattr("routers.resume.compile_to_pdf", _compile)
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf", json={"source": SOURCE})

        assert response.status_code == 503
        assert "connection refused" not in response.text

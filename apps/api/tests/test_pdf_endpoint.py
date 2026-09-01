"""The PDF endpoint and the job behind it.

The endpoint's own job is authorization and translating what the worker raises
into a status code. The queue is stood in for: arq's own delivery is not what
these are checking, so the fake runs the job inline and hands back its result
the way ``job.result()`` would.
"""

from uuid import uuid4

import pytest

from deps.redis import get_arq
from main import app
from services.compiler import CompilerUnavailable, DocumentRejected
from services.compiler_worker import ResumeMissing

PDF = b"%PDF-1.7 fake"


class FakeJob:
    def __init__(self, outcome: bytes | Exception):
        self._outcome = outcome

    async def result(self, timeout: float | None = None) -> bytes:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class FakeQueue:
    """Stands in for ArqRedis, recording what was enqueued."""

    def __init__(self, outcome: bytes | Exception | None):
        self.outcome = outcome
        self.jobs: list[tuple[str, tuple[object, ...]]] = []

    async def enqueue_job(self, function: str, *args: object, **kwargs: object):
        self.jobs.append((function, args))
        return None if self.outcome is None else FakeJob(self.outcome)


@pytest.fixture
def queue(client):
    """Override the queue dependency; set ``.outcome`` to steer the job."""
    fake = FakeQueue(PDF)

    async def override():
        return fake

    app.dependency_overrides[get_arq] = override
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_arq, None)


class TestAuthorization:
    def test_requires_a_session_cookie(self, client, queue):
        response = client.post(f"/resumes/{uuid4()}/pdf")

        assert response.status_code == 401
        assert queue.jobs == []

    def test_hides_another_users_resume(
        self, auth, user, other_user, make_resume, queue
    ):
        resume = make_resume(other_user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 404
        assert queue.jobs == [], "queued a resume the caller does not own"


class TestSuccess:
    def test_returns_the_pdf(self, auth, user, make_resume, queue):
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 200
        assert response.content == PDF
        assert response.headers["content-type"] == "application/pdf"

    def test_queues_the_resume_id_under_the_registered_task_name(
        self, auth, user, make_resume, queue
    ):
        """The name has to match ``generate_resume_pdf.__name__`` or arq drops it."""
        resume = make_resume(user)

        auth(user).post(f"/resumes/{resume.id}/pdf")

        assert queue.jobs == [("generate_resume_pdf", (resume.id,))]

    def test_sends_no_document_of_its_own(self, auth, user, make_resume, queue):
        """The worker reads the rows; nothing about the resume crosses the wire."""
        resume = make_resume(user)

        auth(user).post(f"/resumes/{resume.id}/pdf", json={"source": "\\evil"})

        _, args = queue.jobs[0]
        assert args == (resume.id,)

    def test_names_the_download_after_the_resume(self, auth, user, make_resume, queue):
        resume = make_resume(user, title="Backend Engineer")

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert (
            'filename="backend-engineer.pdf"'
            in (response.headers["content-disposition"])
        )


class TestFailures:
    def test_a_bad_document_comes_back_with_the_log(
        self, auth, user, make_resume, queue
    ):
        queue.outcome = DocumentRejected("! Undefined control sequence.")
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 422
        assert "Undefined control sequence" in response.json()["detail"]

    def test_an_unavailable_engine_does_not_leak_its_message(
        self, auth, user, make_resume, queue
    ):
        queue.outcome = CompilerUnavailable("pdflatex is not installed at /opt/secret")
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 503
        assert "/opt/secret" not in response.text

    def test_a_resume_deleted_mid_job_is_a_404(self, auth, user, make_resume, queue):
        queue.outcome = ResumeMissing(str(uuid4()))
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 404

    def test_a_slow_compile_times_out(self, auth, user, make_resume, queue):
        queue.outcome = TimeoutError()
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 504

    def test_a_queue_that_refuses_the_job_is_unavailable(
        self, auth, user, make_resume, queue
    ):
        queue.outcome = None
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 503

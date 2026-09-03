"""The PDF endpoint and the queue behind it.

The endpoint's own job is authorization, queueing, and translating what the
worker wrote down into a status code. The worker is stood in for — running a
real compile here would test pdfTeX, not this — but the queue is not: the job
row goes into the real table and the outcome is read back out of it, because
that round trip is the part that replaced Redis.
"""

import asyncio
from uuid import uuid4

import pytest

from deps.notify import get_notifier
from enums import PdfJobErrorKind
from main import app
from models.pdf_job import PdfJob
from services import pdf_queue
from services.compiler import CompilerUnavailable, DocumentRejected
from services.pdf_queue import ResumeMissing
from tests.conftest import requires_postgres

# The queue is Postgres and has no SQLite equivalent; the Postgres pass is
# what runs these. See conftest.requires_postgres.
pytestmark = requires_postgres()


PDF = b"%PDF-1.7 fake"

# tells the fake worker to never answer, so the endpoint hits its own timeout
NEVER = object()


class FakeNotifier:
    """Stands in for the listener, playing the worker's part inline.

    ``wait`` is where a worker would have finished the job, so that is where
    this writes the outcome — through the same ``pdf_queue`` calls a real
    worker uses, so the endpoint reads a row that was completed the real way.
    """

    def __init__(self, db):
        self.db = db
        self.outcome: object = PDF
        self.waited: list[object] = []

    def expect(self, job_id):
        return asyncio.get_running_loop().create_future()

    def forget(self, job_id):
        pass

    async def wait(self, job_id, future, timeout):
        self.waited.append(job_id)

        if self.outcome is NEVER:
            raise TimeoutError

        outcome = self.outcome
        if isinstance(outcome, bytes):
            pdf_queue.succeed(self.db, job_id, outcome)
        elif isinstance(outcome, DocumentRejected):
            pdf_queue.fail(self.db, job_id, PdfJobErrorKind.REJECTED, outcome.log)
        elif isinstance(outcome, ResumeMissing):
            pdf_queue.fail(self.db, job_id, PdfJobErrorKind.MISSING, "")
        else:
            pdf_queue.fail(self.db, job_id, PdfJobErrorKind.UNAVAILABLE, str(outcome))


@pytest.fixture
def queue(client, db):
    """Override the notifier; set ``.outcome`` to steer what the worker did."""
    fake = FakeNotifier(db)

    async def override():
        return fake

    app.dependency_overrides[get_notifier] = override
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_notifier, None)


def jobs(db):
    return db.query(PdfJob).all()


class TestAuthorization:
    def test_requires_a_session_cookie(self, client, db, queue):
        response = client.post(f"/resumes/{uuid4()}/pdf")

        assert response.status_code == 401
        assert jobs(db) == []

    def test_hides_another_users_resume(
        self, auth, user, other_user, make_resume, db, queue
    ):
        resume = make_resume(other_user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 404
        assert jobs(db) == [], "queued a resume the caller does not own"


class TestSuccess:
    def test_returns_the_pdf(self, auth, user, make_resume, queue):
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 200
        assert response.content == PDF
        assert response.headers["content-type"] == "application/pdf"

    def test_queues_a_job_for_the_resume(self, auth, user, make_resume, db, queue):
        resume = make_resume(user)

        auth(user).post(f"/resumes/{resume.id}/pdf")

        queued = jobs(db)
        assert [job.resume_id for job in queued] == [resume.id]
        assert queue.waited == [queued[0].id], "waited on a different job"

    def test_sends_no_document_of_its_own(self, auth, user, make_resume, db, queue):
        """The worker reads the rows; nothing about the resume crosses the wire."""
        resume = make_resume(user)

        auth(user).post(f"/resumes/{resume.id}/pdf", json={"source": "\\evil"})

        assert [job.resume_id for job in jobs(db)] == [resume.id]

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
        queue.outcome = CompilerUnavailable("pdflatex is not installed at /opt/tex")
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 503
        assert "/opt/tex" not in response.json()["detail"]

    def test_a_resume_deleted_mid_flight_is_a_404(self, auth, user, make_resume, queue):
        queue.outcome = ResumeMissing("gone")
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 404

    def test_a_job_that_never_finishes_times_out(self, auth, user, make_resume, queue):
        queue.outcome = NEVER
        resume = make_resume(user)

        response = auth(user).post(f"/resumes/{resume.id}/pdf")

        assert response.status_code == 504

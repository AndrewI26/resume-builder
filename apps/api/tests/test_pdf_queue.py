"""The Postgres job queue.

These are the parts that used to be Redis's problem: handing a job to exactly
one worker, carrying a result back, and not letting rows pile up. They run
against the real database because ``FOR UPDATE SKIP LOCKED`` is the whole
mechanism and nothing else reproduces it.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from enums import PdfJobErrorKind, PdfJobStatus
from models.pdf_job import PdfJob
from models.resume import Resume
from models.user import User
from services import pdf_queue
from services.compiler import CompilerUnavailable, DocumentRejected
from services.pdf_queue import ResumeMissing
from tests.conftest import requires_postgres

# The queue is Postgres and has no SQLite equivalent; the Postgres pass is
# what runs these. See conftest.requires_postgres.
pytestmark = requires_postgres()


PDF = b"%PDF-1.7 fake"


@pytest.fixture
def resume(user, make_resume):
    return make_resume(user)


@pytest.fixture
def committed_resume(engine):
    """A resume visible to other connections, cleaned up afterwards.

    Everything else here rides the fixture transaction and is rolled back;
    contention cannot be tested that way, so this one commits and tidies up.
    Deleting the user cascades to the resume and its jobs.
    """
    with Session(engine) as db:
        user = User(email=f"queue-{uuid4()}@example.com", hashed_password="x")
        db.add(user)
        db.flush()

        resume = Resume(
            user_id=user.id,
            title="Contention",
            template="jakes",
            section_order=[],
        )
        db.add(resume)
        db.commit()

        resume_id, user_id = resume.id, user.id

    try:
        yield resume_id
    finally:
        with Session(engine) as db:
            db.query(User).filter(User.id == user_id).delete()
            db.commit()


class TestClaiming:
    def test_a_queued_job_is_claimed_once(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())

        claimed = pdf_queue.claim(db)

        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.resume_id == resume.id

    def test_an_empty_queue_claims_nothing(self, db):
        assert pdf_queue.claim(db) is None

    def test_claiming_marks_the_job_running(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())

        pdf_queue.claim(db)

        job = db.get(PdfJob, job_id)
        assert job.status is PdfJobStatus.RUNNING
        assert job.attempts == 1
        assert job.started_at is not None

    def test_a_claimed_job_is_not_claimed_again(self, db, resume):
        pdf_queue.enqueue(db, resume.id, uuid4())
        pdf_queue.claim(db)

        assert pdf_queue.claim(db) is None

    def test_the_oldest_job_goes_first(self, db, resume):
        first = pdf_queue.enqueue(db, resume.id, uuid4())
        second = pdf_queue.enqueue(db, resume.id, uuid4())

        first_claim = pdf_queue.claim(db)
        second_claim = pdf_queue.claim(db)

        assert first_claim is not None and first_claim.id == first
        assert second_claim is not None and second_claim.id == second


class TestConcurrentWorkers:
    """``SKIP LOCKED`` is what lets the pool scale by adding processes."""

    def test_a_worker_steps_over_a_job_another_holds(self, engine, committed_resume):
        """The second worker must skip the locked row, not queue behind it.

        Two real connections, because one cannot contend with itself, and the
        first keeps its transaction open so the lock is still held when the
        second looks. Without ``SKIP LOCKED`` this does not fail — it hangs,
        which is exactly the production symptom being ruled out.

        The rows have to be committed for another connection to see them, so
        this test owns its data rather than riding the fixture transaction.
        """
        with Session(engine) as setup:
            first = pdf_queue.enqueue(setup, committed_resume, uuid4())
            second = pdf_queue.enqueue(setup, committed_resume, uuid4())

        with Session(engine) as holder, Session(engine) as worker:
            held = holder.execute(
                select(PdfJob).where(PdfJob.id == first).with_for_update()
            ).scalar_one()
            assert held.id == first

            claimed = pdf_queue.claim(worker)

            assert claimed is not None, "blocked on the held row instead of skipping"
            assert claimed.id == second


class TestResults:
    def test_a_finished_job_hands_back_its_pdf(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())
        pdf_queue.claim(db)

        pdf_queue.succeed(db, job_id, PDF)

        assert pdf_queue.result(db, job_id) == PDF

    def test_a_rejection_comes_back_as_the_engines_log(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())

        pdf_queue.fail(db, job_id, PdfJobErrorKind.REJECTED, "! Undefined cs.")

        with pytest.raises(DocumentRejected) as caught:
            pdf_queue.result(db, job_id)

        assert "Undefined cs" in caught.value.log

    def test_a_missing_resume_comes_back_as_missing(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())

        pdf_queue.fail(db, job_id, PdfJobErrorKind.MISSING, "")

        with pytest.raises(ResumeMissing):
            pdf_queue.result(db, job_id)

    def test_an_unavailable_engine_comes_back_as_unavailable(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())

        pdf_queue.fail(db, job_id, PdfJobErrorKind.UNAVAILABLE, "no docker")

        with pytest.raises(CompilerUnavailable):
            pdf_queue.result(db, job_id)

    def test_a_job_that_vanished_reads_as_a_missing_resume(self, db):
        """The resume's cascade can take the row while the request waits."""
        with pytest.raises(ResumeMissing):
            pdf_queue.result(db, uuid4())


class TestReaping:
    def test_finished_rows_are_deleted_once_they_are_stale(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())
        pdf_queue.succeed(db, job_id, PDF)

        _age(db, job_id, finished=pdf_queue.RESULT_TTL + timedelta(seconds=5))
        removed = pdf_queue.reap(db)

        assert removed == 1
        assert db.get(PdfJob, job_id) is None

    def test_a_fresh_result_is_left_for_its_request_to_read(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())
        pdf_queue.succeed(db, job_id, PDF)

        assert pdf_queue.reap(db) == 0
        assert db.get(PdfJob, job_id) is not None

    def test_an_abandoned_job_is_failed_rather_than_left_running(self, db, resume):
        """A worker died mid-compile; its request should not wait the full timeout."""
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())
        pdf_queue.claim(db)

        _age(db, job_id, started=pdf_queue.LEASE + timedelta(seconds=5))
        pdf_queue.reap(db)

        job = db.get(PdfJob, job_id)
        assert job.status is PdfJobStatus.FAILED
        assert job.error_kind is PdfJobErrorKind.UNAVAILABLE

    def test_a_running_job_within_its_lease_is_left_alone(self, db, resume):
        job_id = pdf_queue.enqueue(db, resume.id, uuid4())
        pdf_queue.claim(db)

        pdf_queue.reap(db)

        assert db.get(PdfJob, job_id).status is PdfJobStatus.RUNNING


class TestPending:
    def test_counts_only_the_unfinished(self, db, resume):
        pdf_queue.enqueue(db, resume.id, uuid4())
        done = pdf_queue.enqueue(db, resume.id, uuid4())
        pdf_queue.succeed(db, done, PDF)

        assert pdf_queue.pending(db) == 1


def _age(db, job_id, *, started=None, finished=None):
    """Backdate a job's timestamps so the reaper considers it old."""
    job = db.get(PdfJob, job_id)
    now = datetime.now(UTC)
    if started is not None:
        job.started_at = now - started
    if finished is not None:
        job.finished_at = now - finished
    db.commit()

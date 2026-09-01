"""The workers that turn queued jobs into PDFs.

Typesetting is slow and bursty — a run is CPU-bound for a second or two — so it
does not belong on the request path holding a connection open. The endpoint
queues a job and waits; these claim it and do the work.

They run inside the API process, started by its lifespan, which is what makes
the pool size a property of how the API was started rather than of how many
containers someone remembered to launch. The compile itself is nowhere near
this process: it happens in a container of its own, so "in the API" costs an
``await`` and a pipe, not the engine's blast radius.

A worker is a loop and nothing else. It never fails permanently: every error
inside the loop is recorded against the job and the loop goes back for the next
one, because a worker that exits is a queue that silently stops draining.
"""

import asyncio
import logging
from uuid import UUID

from deps.db import SessionLocal
from deps.notify import PdfNotifier
from enums import PdfJobErrorKind
from models.resume import Resume
from services import pdf_queue
from services.compiler import CompilerUnavailable, DocumentRejected, compile_to_pdf
from services.latex import serialize_to_tex
from services.pdf_queue import ClaimedJob, ResumeMissing
from services.resume_document import build_resume_document

logger = logging.getLogger(__name__)

# How long an idle worker waits before looking again regardless of
# notifications. The wake-up is what makes the queue prompt; this is what makes
# it reliable when a notification is lost.
POLL_INTERVAL = 1.0

# How often terminal rows are swept away. Well under the result TTL, so rows
# never pile up between passes.
REAP_INTERVAL = 30.0


def _build_source(resume_id: UUID) -> str:
    """Read the resume's rows and render them to LaTeX.

    Runs on a thread: the session is the synchronous one the rest of the app
    uses, and blocking the event loop here would stall every other worker.

    The document is assembled from the resume's own rows rather than from
    anything a caller sent, which is what lets the compile trust its input as
    far as it does.
    """
    with SessionLocal() as db:
        resume = db.get(Resume, resume_id)
        if resume is None:
            raise ResumeMissing(str(resume_id))

        return serialize_to_tex(build_resume_document(db, resume))


def _in_session[T](work) -> T:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        return work(db)


async def _record(work) -> None:  # type: ignore[no-untyped-def]
    """Run a pdf_queue write on a thread, without letting it kill the worker."""
    try:
        await asyncio.to_thread(_in_session, work)
    except Exception:
        logger.exception("could not record the outcome of a PDF job")


async def process(job: ClaimedJob) -> None:
    """Compile one claimed job and write down how it went.

    Every failure the endpoint distinguishes is recorded rather than raised:
    the request waiting on this job is in another coroutine and cannot catch
    anything from here.
    """
    try:
        source = await asyncio.to_thread(_build_source, job.resume_id)
    except ResumeMissing:
        # deleted between enqueueing and running
        await _record(
            lambda db: pdf_queue.fail(db, job.id, PdfJobErrorKind.MISSING, "")
        )
        return
    except Exception:
        logger.exception("could not build the document for job %s", job.id)
        await _record(
            lambda db: pdf_queue.fail(
                db, job.id, PdfJobErrorKind.UNAVAILABLE, str(error)
            )
        )
        return

    try:
        pdf = await compile_to_pdf(source)
    except DocumentRejected:
        await _record(
            lambda db: pdf_queue.fail(db, job.id, PdfJobErrorKind.REJECTED, error.log)
        )
        return
    except CompilerUnavailable as error:
        logger.warning("PDF engine unavailable for job %s: %s", job.id, error)
        await _record(
            lambda db: pdf_queue.fail(
                db, job.id, PdfJobErrorKind.UNAVAILABLE, str(error)
            )
        )
        return

    await _record(lambda db: pdf_queue.succeed(db, job.id, pdf))


async def _idle(notifier: PdfNotifier) -> None:
    """Wait for a job to be queued, or for the poll interval, whichever first."""
    notifier.queued.clear()
    try:
        await asyncio.wait_for(notifier.queued.wait(), POLL_INTERVAL)
    except TimeoutError:
        pass


async def worker_loop(notifier: PdfNotifier, name: str) -> None:
    """Claim and compile, forever, until cancelled."""
    logger.info("PDF worker %s started", name)
    while True:
        try:
            job = await asyncio.to_thread(_in_session, pdf_queue.claim)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("PDF worker %s could not claim a job", name)
            await asyncio.sleep(POLL_INTERVAL)
            continue

        if job is None:
            await _idle(notifier)
            continue

        # a burst queues several jobs but only wakes us once, so tell the rest
        # of the pool there may be more where this came from
        notifier.wake_workers()

        await process(job)


async def reaper_loop() -> None:
    """Delete finished rows and rescue abandoned ones, forever."""
    while True:
        await asyncio.sleep(REAP_INTERVAL)
        try:
            await asyncio.to_thread(_in_session, pdf_queue.reap)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("could not reap finished PDF jobs")

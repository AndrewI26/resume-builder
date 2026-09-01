"""One Postgres connection listening on behalf of the whole process.

Two things in the API wait on the queue: a request wants to know its own job
finished, and an idle worker wants to know some job arrived. Both facts travel
as ``NOTIFY``, and both are served here by a single ``LISTEN`` connection.

A connection per waiting request would be the obvious version and the wrong
one — it spends a database connection per concurrent export. Instead this task
holds one, and hands each notification to whoever registered interest.

The listener is a convenience, never the source of truth. Notifications are
lost if the connection drops, so every waiter also has a timeout and every
worker also polls; missing one delays a job rather than stranding it.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import psycopg
from fastapi import Depends, Request
from sqlalchemy import select

from config import get_settings
from deps.db import SessionLocal
from enums import PdfJobStatus
from models.pdf_job import PdfJob
from services.pdf_queue import CHANNEL_DONE, CHANNEL_QUEUED

logger = logging.getLogger(__name__)
settings = get_settings()

# How long to wait before retrying a listen connection that dropped, and the
# ceiling that backoff climbs to.
_RETRY_DELAY = 0.5
_MAX_RETRY_DELAY = 5.0


class PdfNotifier:
    """Wake-ups for the PDF queue: per-job for requests, broadcast for workers."""

    def __init__(self) -> None:
        self._waiters: dict[uuid.UUID, asyncio.Future[None]] = {}
        # workers wait on this; set when a job is queued. A worker that wakes
        # and finds nothing simply goes back to waiting, so a spurious set is
        # harmless and a missed one costs a poll interval.
        self.queued = asyncio.Event()

    def expect(self, job_id: uuid.UUID) -> asyncio.Future[None]:
        """Register interest in a job *before* it is enqueued.

        Registering first is what closes the race: a job that finishes before
        the insert's caller resumes still finds a future here to resolve.
        """
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters[job_id] = future
        return future

    def forget(self, job_id: uuid.UUID) -> None:
        self._waiters.pop(job_id, None)

    async def wait(
        self, job_id: uuid.UUID, future: asyncio.Future[None], timeout: float
    ) -> None:
        """Block until the job reaches a terminal state, or raise TimeoutError."""
        try:
            await asyncio.wait_for(future, timeout)
        finally:
            self.forget(job_id)

    def resolve(self, job_id: uuid.UUID) -> None:
        future = self._waiters.get(job_id)
        if future is not None and not future.done():
            future.set_result(None)

    def wake_workers(self) -> None:
        self.queued.set()

    def _dispatch(self, channel: str, payload: str) -> None:
        if channel == CHANNEL_QUEUED:
            self.wake_workers()
            return

        try:
            self.resolve(uuid.UUID(payload))
        except ValueError:
            logger.warning("ignoring %s notification with payload %r", channel, payload)

    async def _resync(self) -> None:
        """Catch up waiters whose jobs finished while we were disconnected."""
        pending = list(self._waiters)
        if not pending:
            return

        def finished() -> list[uuid.UUID]:
            with SessionLocal() as db:
                return list(
                    db.scalars(
                        select(PdfJob.id).where(
                            PdfJob.id.in_(pending),
                            PdfJob.status.in_(
                                (PdfJobStatus.SUCCEEDED, PdfJobStatus.FAILED)
                            ),
                        )
                    )
                )

        for job_id in await asyncio.to_thread(finished):
            self.resolve(job_id)

        # a job may also have arrived unseen
        self.wake_workers()

    async def run(self) -> None:
        """Hold the LISTEN connection open, reconnecting for as long as we live."""
        delay = _RETRY_DELAY
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    settings.async_database_url, autocommit=True
                ) as connection:
                    await connection.execute(f"LISTEN {CHANNEL_QUEUED}")
                    await connection.execute(f"LISTEN {CHANNEL_DONE}")

                    # anything that happened before this connection existed
                    await self._resync()
                    delay = _RETRY_DELAY

                    async for notification in connection.notifies():
                        self._dispatch(notification.channel, notification.payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("PDF notification listener dropped; reconnecting")

            await asyncio.sleep(delay)
            delay = min(delay * 2, _MAX_RETRY_DELAY)


async def get_notifier(request: Request) -> AsyncGenerator[PdfNotifier, None]:
    """The process-wide notifier, put on app state by the lifespan."""
    yield request.app.state.pdf_notifier


Notifier = Annotated[PdfNotifier, Depends(get_notifier)]

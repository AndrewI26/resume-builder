"""Entrypoint for a standalone PDF worker: ``uv run python worker.py``.

Not needed in development — the API starts its own workers, and
``PDF_WORKER_COUNT`` says how many. This is for the compose deployment, where
the compile runs in a container of its own rather than in a container the API
spawns: the image here ships pdfTeX, so ``LATEX_BACKEND=local`` runs the engine
as a child process and the container is the sandbox.

Same pool as the API runs, pointed at the same table. Nothing coordinates the
two beyond Postgres, which is the point: a job is claimed by whoever gets the
row lock first.
"""

import asyncio
import logging

from config import get_settings
from deps.notify import PdfNotifier
from services.pdf_worker import run_pool

settings = get_settings()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    notifier = PdfNotifier()
    async with run_pool(notifier, settings.pdf_worker_count):
        # nothing else to do here; the pool is the process
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())

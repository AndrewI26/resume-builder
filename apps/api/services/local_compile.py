"""Typesetting for the desktop app, where there is no queue to hand it to.

The hosted API puts compiles on a queue because many people share one host and
a burst of exports would otherwise arrive as a burst of TeX processes. A local
install has neither problem: one person, one machine, and a compile they are
sitting and waiting for. Adding a broker so a single user can queue behind
themselves would be infrastructure bought for nothing.

What does carry over is the bound on concurrency. A compile is CPU-bound for a
second or two, and someone clicking export repeatedly should not be able to
start an unbounded number of them, so the same limit the worker uses applies
here — just held in this process rather than by a broker.
"""

import asyncio
from uuid import UUID

from services.compiler_worker import MAX_CONCURRENT_COMPILES, generate_resume_pdf

_slots = asyncio.Semaphore(MAX_CONCURRENT_COMPILES)


async def compile_resume_pdf_locally(resume_id: UUID) -> bytes:
    """Build the resume's PDF here and now.

    Raises exactly what the queued path raises — ``ResumeMissing``,
    ``DocumentRejected``, ``CompilerUnavailable`` — so the endpoint maps
    failures to responses the same way in both deployments.
    """
    async with _slots:
        return await generate_resume_pdf({}, resume_id)

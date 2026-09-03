"""Typesetting for the desktop app, where there is no queue to hand it to.

The hosted API puts compiles on a queue because many people share one host and
a burst of exports would otherwise arrive as a burst of TeX processes. A local
install has neither problem: one person, one machine, and a compile they are
sitting and waiting for. A queue there would be infrastructure bought for
nothing — and it is a Postgres queue, which a SQLite install does not have.

What does carry over is the bound on concurrency. A compile is CPU-bound for a
second or two, and somebody clicking export repeatedly should not be able to
start an unbounded number of them, so the limit is held in this process rather
than by a queue.

The engine runs in this process too, not in a container: the desktop app
compiles with the TeX it ships, and a container is not the boundary it is on a
server — the whole application is already running on one person's machine.
``Settings`` forces ``latex_backend`` to "local" for that reason.
"""

import asyncio

from sqlalchemy.orm import Session

from models.resume import Resume
from services.compiler import compile_to_pdf
from services.latex import serialize_to_tex
from services.resume_document import build_resume_document

# More at once makes each one slower rather than finishing sooner.
MAX_CONCURRENT_COMPILES = 2

_slots = asyncio.Semaphore(MAX_CONCURRENT_COMPILES)


async def compile_resume_pdf_locally(db: Session, resume: Resume) -> bytes:
    """Build the resume's PDF here and now.

    Raises exactly what the queued path raises — ``DocumentRejected``,
    ``CompilerUnavailable`` — so the endpoint maps failures to responses the
    same way in both deployments. There is no ``ResumeMissing``: the resume was
    loaded to authorize the request and is still in hand.
    """
    document = build_resume_document(db, resume)

    async with _slots:
        return await compile_to_pdf(serialize_to_tex(document))

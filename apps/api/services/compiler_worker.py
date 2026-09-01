"""The arq worker that turns a saved resume into a PDF.

Typesetting is slow and bursty — a run is CPU-bound for a second or two — so it
does not belong on the request path holding a connection open. The endpoint
enqueues a job here and waits for the result; the queue is what keeps a burst
of exports from arriving as a burst of TeX processes.

The job is handed a resume id and nothing else. It reads the rows itself rather
than trusting a document sent in from outside, which is what lets the compile
step drop the token and network fencing the standalone service needed.
"""

from typing import ClassVar
from uuid import UUID

from arq.connections import RedisSettings
from sqlalchemy.orm import Session

from config import get_settings
from deps.db import SessionLocal
from models.resume import Resume
from services.compiler import compile_to_pdf
from services.latex import serialize_to_tex
from services.resume_document import build_resume_document

settings = get_settings()

# One resume is one job, so a retry would re-run a compile that failed for a
# reason retrying cannot change: the document is the same every time.
MAX_TRIES = 1


class ResumeMissing(Exception):
    """The resume was deleted between enqueueing the job and running it."""


def _load(db: Session, resume_id: UUID) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise ResumeMissing(str(resume_id))

    return resume


async def generate_resume_pdf(ctx: dict[str, object], resume_id: UUID) -> bytes:
    """Build a resume's LaTeX and typeset it, returning the PDF bytes.

    Ownership was settled by the endpoint that enqueued this, and the document
    is assembled from that resume's own rows, so there is no caller-supplied
    source to distrust here.
    """
    # patched in tests, so it is looked up on the module rather than bound at
    # import time
    with SessionLocal() as db:
        document = build_resume_document(db, _load(db, resume_id))

    return await compile_to_pdf(serialize_to_tex(document))


class WorkerSettings:
    """What ``arq.worker`` reads to start this worker.

    Started by ``worker.py``, not by the ``arq`` CLI — see the note there.

    arq reads these off the class ``__dict__``, so a subclass that means to
    override one has to restate the rest.
    """

    functions: ClassVar = [generate_resume_pdf]
    max_tries = MAX_TRIES

    # a compile is CPU-bound, so more of them at once makes every one slower
    # rather than finishing sooner
    max_jobs = 2

    # long enough to cover the engine's own 20s ceiling plus the queries
    job_timeout = 30

    # the endpoint waits on the result, so it has to outlive the request
    keep_result = 60

    redis_settings = RedisSettings(
        host="localhost",
        port=settings.redis_port,
        password=settings.redis_password,
        database=0,
    )

"""The job the queue runs.

It is handed nothing but a resume id, so what these check is that it can get
from that id to a real PDF using the database and the engine — the two things
the endpoint tests stand in for.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from enums import ResumeSectionType
from services import compiler_worker
from services.compiler_worker import ResumeMissing, generate_resume_pdf

_PROBE = """
import asyncio, uuid
from services.compiler_worker import generate_resume_pdf, ResumeMissing

try:
    asyncio.run(generate_resume_pdf({}, uuid.uuid4()))
except ResumeMissing:
    print("OK")
"""

needs_latex = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="pdflatex is not installed"
)


@pytest.fixture
def session_factory(db, monkeypatch):
    """Point the worker at the test transaction instead of a fresh session.

    The job closes what it opens, and closing the fixture's session would end
    the transaction the rest of the test runs in, so the context manager here
    is a no-op on the way out.
    """

    class Borrowed:
        def __enter__(self):
            return db

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(compiler_worker, "SessionLocal", Borrowed)


@pytest.mark.anyio
class TestGenerateResumePdf:
    async def test_refuses_a_resume_that_is_gone(self, session_factory, db):
        from uuid import uuid4

        with pytest.raises(ResumeMissing):
            await generate_resume_pdf({}, uuid4())

    @needs_latex
    async def test_builds_a_pdf_from_the_resumes_own_rows(
        self, session_factory, user, make_resume, make_education, attach_section
    ):
        resume = make_resume(user, section_order=[ResumeSectionType.EDUCATION])
        education = make_education(user, name="State University")
        attach_section(resume, ResumeSectionType.EDUCATION, education.id)

        pdf = await generate_resume_pdf({}, resume.id)

        assert pdf.startswith(b"%PDF-")

    @needs_latex
    async def test_a_resume_with_no_sections_still_typesets(
        self, session_factory, user, make_resume
    ):
        """An empty resume is a header on a page, not a compile error."""
        resume = make_resume(user, full_name="Ada Lovelace")

        pdf = await generate_resume_pdf({}, resume.id)

        assert pdf.startswith(b"%PDF-")

    @needs_latex
    async def test_a_title_with_latex_metacharacters_does_not_break_the_compile(
        self, session_factory, user, make_resume, make_education, attach_section
    ):
        resume = make_resume(user, section_order=[ResumeSectionType.EDUCATION])
        education = make_education(user, name="100% & Co_{Ltd}")
        attach_section(resume, ResumeSectionType.EDUCATION, education.id)

        pdf = await generate_resume_pdf({}, resume.id)

        assert pdf.startswith(b"%PDF-")


def test_the_worker_module_configures_mappers_on_its_own():
    """A worker process imports one service, not the whole app.

    The rest of this file cannot catch a missing model import: conftest loads
    ``main``, which pulls in every router and therefore every model. Only a
    fresh interpreter reproduces what arq actually does.
    """
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        check=False,
        text=True,
        cwd=Path(__file__).parent.parent,
    )

    assert "OK" in result.stdout, result.stderr[-1500:]

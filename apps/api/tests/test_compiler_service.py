"""The compile step, in both of the ways it can be fenced.

``docker`` gives each compile a container of its own and is what the API uses
on the host; ``local`` runs the engine as a child process and is what the
worker container uses, where the container is already the boundary. Both are
exercised against the real engine when it is available, so the sandbox flags
are checked against the thing that actually enforces them rather than a stub
that cannot.
"""

import asyncio
import shutil
import subprocess

import pytest

from config import get_settings
from services.compiler import (
    CompilerUnavailable,
    DocumentRejected,
    compile_to_pdf,
)

MINIMAL = r"\documentclass{article}\begin{document}Hi\end{document}"

settings = get_settings()


def _image_available() -> bool:
    docker = shutil.which("docker")
    if docker is None:
        return False

    found = subprocess.run(
        [docker, "image", "inspect", settings.latex_image],
        capture_output=True,
        check=False,
    )
    return found.returncode == 0


needs_image = pytest.mark.skipif(
    not _image_available(),
    reason=f"the {settings.latex_image} image is not built (bun run docker:latex)",
)
needs_latex = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="pdflatex is not installed"
)

# every backend, against the same expectations
backends = pytest.mark.parametrize(
    "backend",
    [
        pytest.param("docker", marks=needs_image),
        pytest.param("local", marks=needs_latex),
    ],
)


@pytest.mark.anyio
@backends
class TestCompile:
    async def test_returns_a_pdf(self, backend):
        pdf = await compile_to_pdf(MINIMAL, backend=backend)

        assert pdf.startswith(b"%PDF-")

    async def test_a_bad_document_carries_the_engine_log(self, backend):
        with pytest.raises(DocumentRejected) as caught:
            await compile_to_pdf(
                r"\documentclass{article}\begin{document}\nope", backend=backend
            )

        assert "Undefined control sequence" in caught.value.log

    async def test_refuses_to_read_a_file_outside_its_directory(self, backend):
        """``openin_any=p`` is what stops a document exfiltrating its host."""
        with pytest.raises(DocumentRejected) as caught:
            await compile_to_pdf(
                r"\documentclass{article}\begin{document}"
                r"\input{/etc/passwd}\end{document}",
                backend=backend,
            )

        assert "root" not in caught.value.log

    async def test_gives_up_on_a_document_that_loops(self, backend):
        source = (
            r"\documentclass{article}\begin{document}"
            r"\newcount\n\loop\advance\n by 1\relax\ifnum\n>0\repeat"
            r"\end{document}"
        )

        with pytest.raises(DocumentRejected) as caught:
            await compile_to_pdf(source, timeout=3.0, backend=backend)

        assert "timed out" in caught.value.log


@pytest.mark.anyio
class TestUnavailable:
    async def test_a_missing_image_is_not_the_documents_fault(self):
        """503, not 422: there was nothing wrong with the resume."""
        with pytest.raises(CompilerUnavailable):
            await compile_to_pdf(MINIMAL, backend="docker", image="no-such-image")

    @needs_latex
    async def test_a_local_run_leaves_nothing_behind(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))

        await compile_to_pdf(MINIMAL, backend="local")

        assert list(tmp_path.iterdir()) == []


@needs_image
@pytest.mark.anyio
class TestContainerIsolation:
    async def test_the_container_is_gone_when_the_compile_times_out(self):
        """A timeout must take the container, not just the client that started it."""
        source = (
            r"\documentclass{article}\begin{document}"
            r"\newcount\n\loop\advance\n by 1\relax\ifnum\n>0\repeat"
            r"\end{document}"
        )

        with pytest.raises(DocumentRejected):
            await compile_to_pdf(source, timeout=3.0, backend="docker")

        running = await asyncio.to_thread(
            subprocess.run,
            ["docker", "ps", "-aq", "--filter", "name=resume-latex-"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert running.stdout.strip() == "", "left a container behind"

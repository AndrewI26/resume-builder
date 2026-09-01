"""The compile step, now that it runs the engine in-process.

These exercise the real pdflatex when one is installed and skip otherwise, so
the sandbox flags are checked against the engine that actually enforces them
rather than against a stub that cannot.
"""

import shutil

import pytest

from services.compiler import (
    CompilerUnavailable,
    DocumentRejected,
    compile_to_pdf,
)

MINIMAL = r"\documentclass{article}\begin{document}Hi\end{document}"

needs_latex = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="pdflatex is not installed"
)


@pytest.mark.anyio
class TestCompile:
    @needs_latex
    async def test_returns_a_pdf(self):
        pdf = await compile_to_pdf(MINIMAL)

        assert pdf.startswith(b"%PDF-")

    @needs_latex
    async def test_a_bad_document_carries_the_engine_log(self):
        with pytest.raises(DocumentRejected) as caught:
            await compile_to_pdf(r"\documentclass{article}\begin{document}\nope")

        assert "Undefined control sequence" in caught.value.log

    @needs_latex
    async def test_refuses_to_read_a_file_outside_its_directory(self):
        """``openin_any=p`` is what stops a document exfiltrating the host."""
        with pytest.raises(DocumentRejected) as caught:
            await compile_to_pdf(
                r"\documentclass{article}\begin{document}"
                r"\input{/etc/passwd}\end{document}"
            )

        assert "root" not in caught.value.log

    @needs_latex
    async def test_gives_up_on_a_document_that_loops(self):
        source = (
            r"\documentclass{article}\begin{document}"
            r"\newcount\n\loop\advance\n by 1\relax\ifnum\n>0\repeat"
            r"\end{document}"
        )

        with pytest.raises(DocumentRejected) as caught:
            await compile_to_pdf(source, timeout=2.0)

        assert "timed out" in caught.value.log

    async def test_reports_a_missing_engine_rather_than_crashing(self):
        with pytest.raises(CompilerUnavailable):
            await compile_to_pdf(MINIMAL, engine="not-a-real-engine")

    @needs_latex
    async def test_leaves_nothing_behind(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))

        await compile_to_pdf(MINIMAL)

        assert list(tmp_path.iterdir()) == []

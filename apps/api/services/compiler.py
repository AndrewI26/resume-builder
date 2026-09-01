"""Turning LaTeX source into a PDF.

Runs the engine as a child process of the worker rather than calling out to a
separate service. The document is generated from the caller's own rows a few
lines earlier, so the trust boundary that justified a standalone container is
gone; what remains is the engine's own behaviour, which is fenced below.

The engine has to be pdfTeX. The template calls ``\\pdfgentounicode``, a pdfTeX
primitive, to emit the glyph-to-Unicode map that makes the PDF readable by
applicant tracking systems — which for a resume is close to the whole point.
XeTeX-based engines such as Tectonic reject it.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

# how much of main.log to keep. It opens with pages of configuration, so the
# part that explains a failure is at the end.
_LOG_TAIL = 4000


class CompilerError(Exception):
    """The base for anything that went wrong producing a PDF."""


class DocumentRejected(CompilerError):
    """The engine could not typeset the source. The document is at fault."""

    def __init__(self, log: str):
        super().__init__("the document failed to compile")
        self.log = log


class CompilerUnavailable(CompilerError):
    """The engine is missing, or the run could not be started."""


def _environment(directory: Path) -> dict[str, str]:
    """A deliberately small environment for the child process.

    The engine inherits nothing the worker was started with, so a stray secret
    in the process environment cannot reach a document that goes looking for
    one.
    """
    return {
        "PATH": os.defpath,
        "HOME": str(directory),
        "TMPDIR": str(directory),
        # TeX wants somewhere writable for generated font files; pointing it at
        # the throwaway directory keeps runs from sharing any state
        "TEXMFVAR": str(directory),
        # paranoid mode: the document cannot read a file outside its own
        # directory and the TeX tree, nor write outside its own directory.
        # This is what stops ``\input{/etc/passwd}`` from reaching the PDF.
        "openin_any": "p",
        "openout_any": "p",
        # pins the timestamp TeX bakes in, so identical input gives an
        # identical file
        "SOURCE_DATE_EPOCH": "0",
        "FORCE_SOURCE_DATE": "1",
    }


def _diagnostics(directory: Path, stderr: str) -> str:
    """Whatever the engine had to say about a failure.

    pdfTeX writes almost everything to main.log rather than stderr, so stderr
    alone usually explains nothing.
    """
    try:
        log = (directory / "main.log").read_text(errors="replace")[-_LOG_TAIL:]
    except OSError:
        return stderr

    return f"{stderr}\n{log}" if stderr else log


async def compile_to_pdf(
    source: str, *, engine: str = "pdflatex", timeout: float = 20.0
) -> bytes:
    """Typeset ``source`` and return the PDF bytes.

    Everything the run touches lives in a directory created for it and removed
    afterwards, so two compiles cannot see each other's files and nothing
    accumulates between them.
    """
    binary = shutil.which(engine)
    if binary is None:
        raise CompilerUnavailable(f"{engine} is not installed")

    with tempfile.TemporaryDirectory(prefix="compile-") as name:
        directory = Path(name)
        (directory / "main.tex").write_text(source, encoding="utf-8")

        try:
            process = await asyncio.create_subprocess_exec(
                binary,
                # never stop to ask a human a question; there is nobody at the
                # terminal
                "-interaction=nonstopmode",
                # give up on the first error rather than cascading through
                # hundreds
                "-halt-on-error",
                # no \write18, no matter what the document contains
                "-no-shell-escape",
                # paths stay relative to cwd below. Paranoid mode refuses
                # absolute ones outright, including the input file's own path,
                # so naming them relatively is what lets the engine read its
                # own input.
                "-output-directory=.",
                "main.tex",
                cwd=directory,
                env=_environment(directory),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                # its own process group, so a timeout can take the engine and
                # anything it spawned rather than orphaning them
                start_new_session=True,
            )
        except OSError as error:
            raise CompilerUnavailable(f"could not start {engine}: {error}") from error

        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except TimeoutError:
            _terminate(process)
            raise DocumentRejected(f"timed out after {timeout:g}s") from None

        if process.returncode != 0:
            raise DocumentRejected(
                _diagnostics(directory, stderr.decode(errors="replace"))
            )

        try:
            return (directory / "main.pdf").read_bytes()
        except OSError:
            # a zero exit with no PDF means the engine gave up quietly
            raise DocumentRejected(
                _diagnostics(directory, stderr.decode(errors="replace"))
            ) from None


def _terminate(process: asyncio.subprocess.Process) -> None:
    """Kill the engine's whole process group, ignoring one that already died."""
    try:
        os.killpg(os.getpgid(process.pid), 9)
    except (ProcessLookupError, PermissionError):
        pass

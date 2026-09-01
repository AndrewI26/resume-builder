"""Turning LaTeX source into a PDF, inside a container built for the purpose.

A TeX document is a program, and the engine that runs it is the least
trustworthy thing in this application. It used to run as a child process of the
worker, fenced with environment variables and paranoid mode. Now each compile
gets a container of its own: no network, a read-only filesystem, no
capabilities, its own memory and process ceilings, and nothing mounted in. It
starts, reads a document on stdin, writes a PDF to stdout, and is gone.

The engine has to be pdfTeX. The template calls ``\\pdfgentounicode``, a pdfTeX
primitive, to emit the glyph-to-Unicode map that makes the PDF readable by
applicant tracking systems — which for a resume is close to the whole point.
XeTeX-based engines such as Tectonic reject it.
"""

import asyncio
import shutil
import uuid

from config import get_settings

settings = get_settings()

# how much of the engine's log to keep. It opens with pages of configuration,
# so the part that explains a failure is at the end.
_LOG_TAIL = 4000

# The container exits 3, and only 3, when the document is at fault. Docker's own
# failures use its exit codes, which is what keeps "your resume will not
# typeset" apart from "there is no engine to typeset it with".
_REJECTED = 3

# What the sandbox is allowed. A resume compiles in well under a second and a
# few tens of megabytes; these are generous and still far short of enough to
# trouble the host.
_LIMITS = (
    # a document has no business talking to anything, and the image needs
    # nothing at runtime
    "--network=none",
    "--read-only",
    # the one writable place, and it dies with the container
    "--tmpfs=/tmp:size=256m,mode=1777,exec",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--memory=512m",
    # a fork bomb in a document should hit a wall, not the host's process table
    "--pids-limit=128",
)


class CompilerError(Exception):
    """The base for anything that went wrong producing a PDF."""


class DocumentRejected(CompilerError):
    """The engine could not typeset the source. The document is at fault."""

    def __init__(self, log: str):
        super().__init__("the document failed to compile")
        self.log = log


class CompilerUnavailable(CompilerError):
    """The engine is missing, or the run could not be started."""


async def compile_to_pdf(
    source: str, *, image: str | None = None, timeout: float = 20.0
) -> bytes:
    """Typeset ``source`` in a throwaway container and return the PDF bytes.

    The document goes in on stdin and the PDF comes back on stdout, so there is
    nothing on disk for two compiles to share and nothing mounted for one to
    escape through.
    """
    docker = shutil.which("docker")
    if docker is None:
        raise CompilerUnavailable("docker is not installed")

    # named so a run that outlives its timeout can still be found and killed;
    # killing the client alone would leave the container behind
    name = f"resume-latex-{uuid.uuid4().hex}"

    try:
        process = await asyncio.create_subprocess_exec(
            docker,
            "run",
            "--rm",
            # stdin is the document; there is no terminal here
            "--interactive",
            f"--name={name}",
            *_LIMITS,
            image or settings.latex_image,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as error:
        raise CompilerUnavailable(f"could not start docker: {error}") from error

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(source.encode("utf-8")), timeout
        )
    except TimeoutError:
        await _kill(docker, name, process)
        raise DocumentRejected(f"timed out after {timeout:g}s") from None

    log = stderr.decode(errors="replace")[-_LOG_TAIL:]

    if process.returncode == _REJECTED:
        raise DocumentRejected(log)

    if process.returncode != 0:
        # 125 is "no such image" or an unreachable daemon; 137 is the kernel
        # taking the container out. None of them are the resume's fault.
        raise CompilerUnavailable(
            f"docker exited {process.returncode}: {log}"
            if log
            else "the compile did not run"
        )

    if not stdout.startswith(b"%PDF-"):
        # a clean exit with no PDF means the engine gave up quietly
        raise DocumentRejected(log or "the engine produced no PDF")

    return stdout


async def _kill(docker: str, name: str, process: asyncio.subprocess.Process) -> None:
    """Remove a container that outstayed its welcome, and reap its client.

    ``docker run`` is only a client; killing it would orphan the container it
    started, which would go on burning a core until it finished.
    """
    try:
        killer = await asyncio.create_subprocess_exec(
            docker,
            "rm",
            "--force",
            name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    except OSError:
        pass

    if process.returncode is None:
        process.kill()

    await process.wait()

"""Turning LaTeX source into a PDF.

A TeX document is a program, and the engine that runs it is the least
trustworthy thing here. There are two ways to fence it, and which one applies
depends on what the process running this is already inside:

``docker``
    Each compile gets a container of its own — no network, read-only root, no
    capabilities, its own memory and process ceilings, nothing mounted in. This
    is the default, and it is what the API uses when it runs on the host in
    development: a compile is then isolated from the machine it was started on.

``local``
    The engine runs as a child process, fenced with paranoid mode and a
    stripped environment. Used *inside* the worker container, where the
    container is already the boundary and starting another one would mean
    handing the worker a Docker socket — which would trade a sandbox for a
    privilege far larger than the one being contained.

Both paths raise the same three exceptions, so nothing above this module has to
know which one ran.

The engine has to be pdfTeX. The template calls ``\\pdfgentounicode``, a pdfTeX
primitive, to emit the glyph-to-Unicode map that makes the PDF readable by
applicant tracking systems — which for a resume is close to the whole point.
XeTeX-based engines such as Tectonic reject it.
"""

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from config import get_settings

settings = get_settings()

# how much of the engine's log to keep. It opens with pages of configuration,
# so the part that explains a failure is at the end.
_LOG_TAIL = 4000

# The container exits 3, and only 3, when the document is at fault. Docker's
# own failures use its exit codes, which is what keeps "this resume will not
# typeset" apart from "there was no engine to typeset it with".
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
    # the sandbox image is built locally, never fetched. Without this a wrong
    # or missing image name sends Docker to a registry, and the compile's own
    # timeout then reports a slow network as a broken document.
    "--pull=never",
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


def _with_bundled_tex(path: str) -> str:
    """``path``, preceded by the bundled TeX distribution if there is one.

    A server has a TeX distribution installed where the process can already see
    it — or runs the engine in a container that does. A desktop install has
    neither: most people have never had a reason to install LaTeX, so the app
    ships its own, and ``texlive_bin`` says where it ended up, which is inside
    the application bundle and so different on every machine.
    """
    if settings.texlive_bin is None:
        return path

    return os.pathsep.join([str(settings.texlive_bin), path])


def _lookup_path() -> str:
    """Where to look for the engine, which is the environment this runs in.

    Deliberately not the path the child is given. Finding the binary is this
    process' business and it may use everything it knows; what the engine then
    inherits is a different and much smaller question.
    """
    return _with_bundled_tex(os.environ.get("PATH", os.defpath))


async def compile_to_pdf(
    source: str,
    *,
    timeout: float = 20.0,
    backend: str | None = None,
    image: str | None = None,
) -> bytes:
    """Typeset ``source`` and return the PDF bytes.

    ``backend`` and ``image`` default to the configured ones and are only
    passed explicitly by the tests that exercise each path.
    """
    if (backend or settings.latex_backend) == "local":
        return await _compile_locally(source, timeout=timeout)

    return await _compile_in_container(source, timeout=timeout, image=image)


async def _compile_in_container(
    source: str, *, timeout: float, image: str | None = None
) -> bytes:
    """Run the engine in a throwaway container.

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
        await _remove_container(docker, name, process)
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


async def _remove_container(
    docker: str, name: str, process: asyncio.subprocess.Process
) -> None:
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


def _environment(directory: Path) -> dict[str, str]:
    """A deliberately small environment for the child process.

    The engine inherits nothing the worker was started with, so a stray secret
    in the process environment cannot reach a document that goes looking for
    one.
    """
    return {
        "PATH": _with_bundled_tex(os.defpath),
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


async def _compile_locally(
    source: str, *, timeout: float, engine: str = "pdflatex"
) -> bytes:
    """Run the engine as a child process, fenced by paranoid mode.

    Everything the run touches lives in a directory created for it and removed
    afterwards, so two compiles cannot see each other's files and nothing
    accumulates between them.
    """
    binary = shutil.which(engine, path=_lookup_path())
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

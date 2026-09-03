"""Export every one of a user's resumes to PDFs in a directory.

Run with ``bun run resumes:export <email> <directory>``.

Compiles directly rather than through the job queue: the queue exists to bound
how many exports a live API serves at once, which a one-off local run does not
need, and going direct means the script works without the API running. It still
uses the configured sandbox, so ``bun run docker:latex`` applies here too.

The directory is emptied of PDFs first, so what lands there is the export and
nothing else. That is destructive, hence the prompt.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from models.resume import Resume
from models.user import User
from services.compiler import CompilerError, compile_to_pdf
from services.latex import serialize_to_tex
from services.resume_document import build_resume_document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export all of a user's resumes as PDFs into a directory."
    )
    parser.add_argument("email", help="the email of the user whose resumes to export")
    parser.add_argument(
        "directory",
        type=Path,
        help="directory to write the PDFs into; existing PDFs in it are deleted",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="skip the confirmation prompt, for non-interactive use",
    )
    return parser.parse_args()


def slug(title: str) -> str:
    """A safe file stem derived from a resume's title.

    Matches the download name ``/resumes/{id}/pdf`` sends, so a file exported
    here is named the same as one saved from the app.
    """
    stem = "".join(
        character if character.isalnum() else "-" for character in title
    ).strip("-")
    return stem.lower() or "resume"


def filenames(titles: list[str]) -> list[str]:
    """One ``.pdf`` name per title, in order, with collisions numbered.

    Titles are not unique — a user can have two resumes both called "Backend" —
    and letting one overwrite the other would drop an export without saying so.
    """
    seen: dict[str, int] = {}
    names: list[str] = []

    for title in titles:
        stem = slug(title)
        count = seen.get(stem, 0)
        seen[stem] = count + 1
        names.append(f"{stem}.pdf" if count == 0 else f"{stem}-{count + 1}.pdf")

    return names


def load_resumes(db: Session, email: str) -> tuple[User, list[Resume]]:
    user = db.scalars(select(User).where(User.email == email)).one_or_none()
    if user is None:
        raise LookupError(f"no user with email {email!r}")

    resumes = list(
        db.scalars(
            select(Resume).where(Resume.user_id == user.id).order_by(Resume.title)
        )
    )
    return user, resumes


def existing_pdfs(directory: Path) -> list[Path]:
    """The PDFs this run would delete.

    Only files sitting directly in the directory, and only PDFs: the target may
    be a folder the user keeps other things in, and nothing here has any
    business removing those.
    """
    if not directory.exists():
        return []

    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def confirm(email: str, directory: Path, resume_count: int, doomed: int) -> bool:
    print(f"About to export {resume_count} resume(s) for {email} to {directory}")

    if doomed:
        print(
            f"WARNING: this overwrites the folder's contents — {doomed} existing "
            "PDF(s) will be permanently deleted, including any this script did "
            "not write."
        )
    else:
        print("The folder has no PDFs in it, so nothing will be deleted.")

    return input("Are you sure? [y/N] ").strip().lower() in {"y", "yes"}


async def export(db: Session, resumes: list[Resume], directory: Path) -> int:
    """Compile each resume into ``directory``. Returns a process exit code.

    A resume that will not export is reported and skipped rather than
    abandoning the ones queued behind it, but it still fails the run so a
    scripted caller notices. That covers assembling the document as well as
    typesetting it, since a row the renderer chokes on fails just as readily as
    a document the engine rejects.
    """
    failed = 0

    for resume, name in zip(resumes, filenames([row.title for row in resumes])):
        try:
            document = build_resume_document(db, resume)
            pdf = await compile_to_pdf(serialize_to_tex(document))
        except (CompilerError, ValidationError) as error:
            print(f"  {name}: FAILED ({error})", file=sys.stderr)
            failed += 1
            continue

        (directory / name).write_bytes(pdf)
        print(f"  {name}")

    if failed:
        print(f"{failed} resume(s) failed to compile", file=sys.stderr)

    return 1 if failed else 0


def main() -> int:
    args = parse_args()
    directory: Path = args.directory.expanduser().resolve()

    if directory.exists() and not directory.is_dir():
        print(f"not a directory: {directory}", file=sys.stderr)
        return 1

    # Imported here so a bad argument is reported before we try to connect:
    # deps.db builds its engine at import time.
    from deps.db import SessionLocal

    try:
        with SessionLocal() as db:
            try:
                user, resumes = load_resumes(db, args.email)
            except LookupError as error:
                print(error, file=sys.stderr)
                return 1

            if not resumes:
                print(f"{user.email} has no resumes; nothing to export")
                return 0

            # Resolved before the prompt so the warning can say how many files
            # are actually at stake.
            doomed = existing_pdfs(directory)

            if not args.yes and not confirm(
                user.email, directory, len(resumes), len(doomed)
            ):
                print("aborted")
                return 1

            directory.mkdir(parents=True, exist_ok=True)
            for path in doomed:
                path.unlink()

            return asyncio.run(export(db, resumes, directory))
    except OperationalError as error:
        print(f"could not connect to the database: {error}", file=sys.stderr)
        print("is `bun run docker:dev` running?", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

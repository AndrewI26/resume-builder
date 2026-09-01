"""Write a compressed dump of the Postgres database to a directory.

Run with ``bun run db:backup <directory>``. The dump is a ``pg_dump`` custom
archive named ``<database>-<UTC timestamp>.dump``, restorable with::

    pg_restore --clean --if-exists -d <database> <file>

``pg_dump`` runs from the host when it is installed; otherwise the copy inside
the ``postgres`` compose container runs instead, so a machine with only Docker
still works.
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from config import Settings, get_settings

COMPOSE_FILE = Path(__file__).resolve().parents[3] / "docker-compose.dev.yml"
COMPOSE_SERVICE = "postgres"


def parse_args() -> Path:
    parser = argparse.ArgumentParser(description="Back up the Postgres database.")
    parser.add_argument(
        "directory",
        type=Path,
        help="directory to write the dump into; created if it does not exist",
    )
    args = parser.parse_args()
    directory: Path = args.directory
    return directory


def dump_command(settings: Settings) -> tuple[list[str], dict[str, str]]:
    """The argv and extra environment for a dump written to stdout.

    stdout rather than ``--file`` because in the container branch that path
    would name a file inside the container; writing to stdout lets the caller
    redirect both branches the same way.
    """
    args = [
        "--format=custom",
        f"--username={settings.postgres_user}",
        settings.postgres_db,
    ]

    if shutil.which("pg_dump"):
        command = [
            "pg_dump",
            "--host=localhost",
            f"--port={settings.postgres_port}",
            *args,
        ]
        return command, {"PGPASSWORD": settings.postgres_password}

    command = [
        "docker",
        "compose",
        "--file",
        str(COMPOSE_FILE),
        "exec",
        "--no-TTY",
        "--env",
        f"PGPASSWORD={settings.postgres_password}",
        COMPOSE_SERVICE,
        "pg_dump",
        *args,
    ]
    return command, {}


def main() -> int:
    directory = parse_args()
    settings = get_settings()

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"could not create {directory}: {error}", file=sys.stderr)
        return 1

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = directory / f"{settings.postgres_db}-{stamp}.dump"

    command, extra_env = dump_command(settings)

    with destination.open("wb") as out:
        result = subprocess.run(
            command, stdout=out, env={**os.environ, **extra_env}, check=False
        )

    if result.returncode != 0:
        # A partial file is worse than none: it still looks like a backup.
        destination.unlink(missing_ok=True)
        print(
            f"pg_dump failed (exit {result.returncode}); "
            "is `bun run docker:dev` running?",
            file=sys.stderr,
        )
        return 1

    print(f"wrote {destination} ({destination.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

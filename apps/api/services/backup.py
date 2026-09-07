"""Taking a copy of a desktop install's database.

Local mode keeps everything in one SQLite file next to the app's own data, and
that file is the only copy of a person's entire library. This makes another
one, on demand, in a ``backups`` folder beside it.

Why ``VACUUM INTO`` rather than copying the file
------------------------------------------------
Because the database is open and being written to while the copy is taken.
Copying the file with the shell, or from the desktop process, reads it in
chunks that can straddle a write, and in WAL mode the newest commits are not in
the main file at all — so what lands is a file that looks like a backup and may
not open. ``VACUUM INTO`` is SQLite's own answer: it writes a complete,
consistent snapshot of the database as of one point in time, through the same
connection that would see any concurrent write, and it compacts it on the way.

The hosted deployment has nothing to do with this. It runs Postgres, is backed
up by ``scripts/backup_db.py`` with ``pg_dump``, and never reaches this code —
the router is only mounted in local mode.
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from config import get_settings

settings = get_settings()

BACKUP_SUFFIX = ".sqlite"


class BackupFailed(Exception):
    """The snapshot could not be written. Carries something worth showing."""


def backup_directory() -> Path:
    """Where backups live: beside the database, not inside someone's Documents.

    The app's own data directory is the honest place for these. It survives
    upgrades, it is per-user, and it is somewhere the app is already entitled
    to write — none of which is true of a folder chosen out in the open.
    """
    return settings.local_data_dir / "backups"


def _destination(now: datetime) -> Path:
    # Second resolution, UTC, sortable: two backups in the same second would
    # collide, which is why the caller refuses rather than silently overwriting
    # — a backup that quietly replaced a different one is a lost backup.
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    return backup_directory() / f"resume-builder-{stamp}{BACKUP_SUFFIX}"


def create_backup(engine: Engine) -> Path:
    """Write a snapshot of the database and return where it went.

    Goes through the driver's own connection rather than a SQLAlchemy one,
    because ``VACUUM`` cannot run inside a transaction and every route into it
    through the session machinery opens one: ``prepare_sqlite`` installs a
    ``begin`` listener that issues a literal ``BEGIN``, and it fires on the
    implicit transaction a plain ``connect()`` starts even when the isolation
    level is set to autocommit. The raw connection has none of that, and the
    same ``prepare_sqlite`` has already left pysqlite in a mode where it does
    not open transactions of its own accord.
    """
    if not settings.is_local:
        raise BackupFailed("only a local install keeps its database in a file")

    destination = _destination(datetime.now(UTC))

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise BackupFailed(f"could not create {destination.parent}: {error}") from error

    if destination.exists():
        # SQLite refuses to vacuum into a file that exists, and it is right to:
        # the previous backup from this same second is not ours to replace.
        raise BackupFailed("a backup was just taken; try again in a moment")

    try:
        connection = engine.raw_connection()
        try:
            cursor = connection.cursor()
            try:
                # Bound rather than interpolated: the path is built here and not
                # from a request, but a quoted string in SQL assembled by hand is
                # a habit worth not having.
                cursor.execute("VACUUM INTO ?", (str(destination),))
            finally:
                cursor.close()
        finally:
            connection.close()
    except Exception as error:
        # A partial file is worse than none: it still looks like a backup.
        destination.unlink(missing_ok=True)
        raise BackupFailed(str(error)) from error

    return destination

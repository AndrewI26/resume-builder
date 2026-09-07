"""Backing up the desktop app's database.

Mounted only in local mode. There is nothing here for the hosted deployment:
it runs Postgres, and its backups are ``pg_dump`` archives taken by
``scripts/backup_db.py`` from somewhere with credentials — not something a
browser tab gets to ask for.

No path comes in from the caller. Where backups go is the server's decision,
which keeps this from becoming a way to write a file anywhere on the machine
that the app happens to have permission for.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from deps.auth import CurrentUser
from deps.db import engine
from schemas.backup import BackupRead
from services.backup import BackupFailed, backup_directory, create_backup

router = APIRouter(prefix="/backup", tags=["Backup"])


@router.post("/", response_model=BackupRead, status_code=status.HTTP_201_CREATED)
def create_database_backup(current_user: CurrentUser) -> BackupRead:
    """Write a snapshot of the database and say where it landed.

    `current_user` is not read: the file is the whole database rather than one
    person's rows, and in local mode there is exactly one person. It is there
    so the endpoint sits behind the same door as everything else — a local
    install still refuses requests that do not carry the shell's token.
    """
    try:
        path = create_backup(engine)
    except BackupFailed as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    stat = path.stat()

    return BackupRead(
        filename=path.name,
        path=str(path),
        directory=str(backup_directory()),
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime, UTC),
    )

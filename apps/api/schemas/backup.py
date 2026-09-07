from datetime import datetime

from pydantic import BaseModel


class BackupRead(BaseModel):
    """A snapshot that now exists on disk."""

    filename: str
    # The full path, because the whole point of the reply is telling someone
    # where their backup went — a name alone sends them looking for it.
    path: str
    directory: str
    size_bytes: int
    created_at: datetime

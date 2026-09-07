"""Backing up a desktop install's database.

The interesting property is not that a file appears — it is that the file is a
usable database holding what the original held. A copy taken the obvious way
can pass the first check and fail the second, which is why these open the
result and read from it rather than looking at its size.
"""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text

import services.backup
from db import prepare_sqlite
from services.backup import BackupFailed, backup_directory, create_backup


@pytest.fixture
def local_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    """A SQLite database in local mode, set up the way the app sets one up."""
    monkeypatch.setattr(services.backup.settings, "mode", "local")
    monkeypatch.setattr(services.backup.settings, "local_data_dir", tmp_path)

    engine = prepare_sqlite(
        create_engine(f"sqlite+pysqlite:///{tmp_path / 'resume-builder.sqlite'}")
    )

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE note (body TEXT)"))
        connection.execute(text("INSERT INTO note VALUES ('keep me')"))

    return engine


class TestCreateBackup:
    def test_writes_into_a_backups_folder_beside_the_database(
        self, local_db: Engine, tmp_path: Path
    ) -> None:
        path = create_backup(local_db)

        assert path.parent == tmp_path / "backups" == backup_directory()
        assert path.name.startswith("resume-builder-")
        assert path.suffix == ".sqlite"

    def test_the_backup_is_a_sound_database_with_the_data_in_it(
        self, local_db: Engine
    ) -> None:
        """The whole point. A torn copy fails here and nowhere else."""
        path = create_backup(local_db)

        copy = sqlite3.connect(path)
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copy.execute("SELECT body FROM note").fetchone()[0] == "keep me"

    def test_it_leaves_the_database_open_for_business(self, local_db: Engine) -> None:
        """VACUUM cannot run in a transaction, so getting this wrong is easy —
        and the failure mode is the app being unusable after a backup."""
        create_backup(local_db)

        with local_db.begin() as connection:
            connection.execute(text("INSERT INTO note VALUES ('after')"))

        with local_db.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM note")).scalar() == 2

    def test_a_second_backup_does_not_replace_the_first(
        self, local_db: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two in the same second collide, and a backup that silently ate
        another one is a lost backup."""
        first = create_backup(local_db)
        monkeypatch.setattr(services.backup, "_destination", lambda _now: first)

        with pytest.raises(BackupFailed, match="just taken"):
            create_backup(local_db)

        assert first.exists()

    def test_it_refuses_when_the_database_is_not_a_local_file(
        self, local_db: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Postgres is backed up with pg_dump; there is no file to snapshot."""
        monkeypatch.setattr(services.backup.settings, "mode", "cloud")

        with pytest.raises(BackupFailed, match="local install"):
            create_backup(local_db)

    def test_a_failed_snapshot_leaves_no_file_behind(
        self, local_db: Engine, tmp_path: Path
    ) -> None:
        """A partial file is worse than none: it still looks like a backup."""
        local_db.dispose()
        (tmp_path / "resume-builder.sqlite").write_text("not a database")

        with pytest.raises(BackupFailed):
            create_backup(local_db)

        assert list((tmp_path / "backups").glob("*.sqlite")) == []

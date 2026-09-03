"""Getting a local database ready before the first request reaches it.

The hosted API is handed a database somebody else already migrated — compose
runs ``alembic upgrade head`` in its own step so nothing races. A desktop
install has no such step and nobody to run it: the first launch after an
install finds no file at all, and the app has to be usable a moment later.

Why a fresh database is created rather than migrated
----------------------------------------------------
The existing revisions were written against Postgres, several of them naming
types SQLite has never had, so replaying that history here would fail on the
first one. It would also be pointless: the history exists to carry a database
that already holds data from one shape to the next, and this one holds nothing.
So a new file gets the current schema directly and is then stamped as being at
head, which is true — it is the schema head describes.

That stamp is what makes later revisions work normally. A database created this
week is at head; when a future version of the app adds a revision, ``upgrade``
finds exactly one to apply. Those revisions have to be written portably, which
is what the column types in ``db.py`` are for.
"""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, inspect

import models  # noqa: F401  (registers every table on Base.metadata)
from alembic import command
from config import get_settings
from db import Base

settings = get_settings()

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_config() -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def bootstrap_local_database(engine: Engine) -> None:
    """Make sure the local database exists and is at the current schema."""
    settings.local_data_dir.mkdir(parents=True, exist_ok=True)

    # the file itself is created by connecting, so its presence says nothing;
    # what matters is whether the schema was ever put into it
    if inspect(engine).has_table("users"):
        command.upgrade(_alembic_config(), "head")
        return

    Base.metadata.create_all(engine)
    command.stamp(_alembic_config(), "head")

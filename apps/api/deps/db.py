from collections.abc import Generator
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings
from db import prepare_sqlite

settings = get_settings()


def _engine_options() -> dict[str, Any]:
    """What the engine needs that differs between the two databases.

    SQLite's driver refuses by default to let a connection be used from a
    thread other than the one that opened it, which is exactly what happens
    here: FastAPI runs the sync endpoints in a threadpool. The connection is
    still only ever used by one request at a time — the pool sees to that —
    so the check is guarding against something that cannot occur.
    """
    if settings.is_local:
        return {"connect_args": {"check_same_thread": False}}

    return {}


engine = prepare_sqlite(create_engine(settings.database_url, **_engine_options()))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Db = Annotated[Session, Depends(get_db)]

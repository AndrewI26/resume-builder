"""The column types in ``db.py``, checked on both databases the app runs on.

The rest of the suite exercises these types incidentally, through the
endpoints, and would keep passing if SQLite quietly stored something Postgres
would not — a list of UUIDs turned into strings and never turned back, say.
These tests are the direct statement of what a portable column has to do, run
against each dialect in turn so a difference between them fails here rather
than a year later in a sync.

The Postgres runs are skipped when there is no server to talk to, so this file
is still meaningful on a laptop with nothing started.
"""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from db import Base, prepare_sqlite
from models.bullet_points import BulletPoint
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.user import User
from tests.conftest import _create_database_if_missing, postgres_url


def _engine(dialect: str, tmp_path_factory: pytest.TempPathFactory) -> Engine:
    if dialect == "sqlite":
        path = tmp_path_factory.mktemp("portable") / "portable.sqlite"
        return prepare_sqlite(create_engine(f"sqlite+pysqlite:///{path}"))

    # a database of its own: this fixture creates and drops the whole schema,
    # which would pull the tables out from under the rest of the suite if it
    # shared their test database
    url = f"{postgres_url()}_types"
    try:
        _create_database_if_missing(url)
    except OperationalError as error:
        pytest.skip(f"no Postgres to test against: {error}")

    return create_engine(url)


@pytest.fixture(params=["sqlite", "postgresql"])
def session(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> object:
    """A session on a schema of its own, one per dialect under test."""
    engine = _engine(request.param, tmp_path_factory)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def _user(session: Session) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="x")
    session.add(user)
    session.commit()
    return user


def test_a_list_of_uuids_comes_back_as_uuids(session: Session) -> None:
    """The case a plain JSON column would get wrong.

    ``json`` cannot encode a ``uuid.UUID`` at all, so SQLite stores these as
    strings; the point of ``UuidArray`` is that nothing above the column ever
    finds that out.
    """
    ids = [uuid.uuid4() for _ in range(3)]
    experience = Expirence(
        user_id=_user(session).id,
        company="Acme",
        position="Engineer",
        bullet_points=ids,
    )
    session.add(experience)
    session.commit()
    experience_id = experience.id
    session.expunge_all()

    stored = session.scalar(select(Expirence).where(Expirence.id == experience_id))
    assert stored is not None
    assert stored.bullet_points == ids
    assert all(isinstance(item, uuid.UUID) for item in stored.bullet_points)


def test_an_empty_uuid_list_stays_an_empty_list(session: Session) -> None:
    """An empty list must not come back as null — the columns are not nullable."""
    experience = Expirence(
        user_id=_user(session).id, company="Acme", position="Engineer"
    )
    session.add(experience)
    session.commit()
    experience_id = experience.id
    session.expunge_all()

    stored = session.scalar(select(Expirence).where(Expirence.id == experience_id))
    assert stored is not None
    assert stored.bullet_points == []


def test_a_json_object_round_trips(session: Session) -> None:
    link = {"url": "https://example.com", "label": "Portfolio"}
    info = PersonalInfo(user_id=_user(session).id, github=link)
    session.add(info)
    session.commit()
    info_id = info.id
    session.expunge_all()

    stored = session.scalar(select(PersonalInfo).where(PersonalInfo.id == info_id))
    assert stored is not None
    assert stored.github == link


def test_nested_json_round_trips(session: Session) -> None:
    """Bullet bolding is a list of ranges, so the nesting has to survive."""
    bullet = BulletPoint(text="Did the thing", bolded=[[0, 3], [4, 7]])
    session.add(bullet)
    session.commit()
    bullet_id = bullet.id
    session.expunge_all()

    stored = session.scalar(select(BulletPoint).where(BulletPoint.id == bullet_id))
    assert stored is not None
    assert stored.bolded == [[0, 3], [4, 7]]


def test_timestamps_come_back_aware_and_in_utc(session: Session) -> None:
    """SQLite has no timezone of its own; the column supplies one."""
    user_id = _user(session).id
    session.expunge_all()

    stored = session.get(User, user_id)
    assert stored is not None
    assert stored.created_at.tzinfo is not None
    assert stored.created_at.utcoffset() == timedelta(0)

    # and it is the actual time, not a naive local reading relabelled as UTC
    assert abs(stored.created_at - datetime.now(UTC)) < timedelta(minutes=5)


def test_an_aware_timestamp_keeps_its_instant(session: Session) -> None:
    """A value written in another zone reads back as the same moment in UTC."""
    written = datetime(2024, 3, 1, 12, 0, tzinfo=timezone(timedelta(hours=-5)))
    user = User(email=f"{uuid.uuid4()}@example.com", created_at=written)
    session.add(user)
    session.commit()
    user_id = user.id
    session.expunge_all()

    stored = session.get(User, user_id)
    assert stored is not None
    assert stored.created_at == written
    assert stored.created_at.utcoffset() == timedelta(0)


def test_deleting_a_user_cascades_to_their_sections(session: Session) -> None:
    """SQLite ignores ``ON DELETE CASCADE`` unless foreign keys are switched on.

    The section routers lean on the database for this, so without
    ``prepare_sqlite`` a local delete would leave rows the hosted app would
    have removed.
    """
    user_id = _user(session).id
    session.add(Expirence(user_id=user_id, company="Acme", position="Engineer"))
    session.commit()

    session.execute(delete(User).where(User.id == user_id))
    session.commit()

    remaining = session.scalars(
        select(Expirence).where(Expirence.user_id == user_id)
    ).all()
    assert remaining == []

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    JSON,
    DateTime,
    Dialect,
    Engine,
    String,
    TypeDecorator,
    Uuid,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeEngine


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Persist each member's value; SQLAlchemy would otherwise store its name.

    Pass to ``Enum(..., values_callable=enum_values)`` so a member written as
    ``EDUCATION = "education"`` reaches the database as ``education`` rather
    than ``EDUCATION``.
    """
    return [member.value for member in enum_cls]


# ---------------------------------------------------------------------------
# Column types that work on both Postgres and SQLite.
#
# The same models back two deployments: the hosted API on Postgres, and the
# desktop app's local database, which is a SQLite file with no server to talk
# to. So no column may name a type only one of them has. Postgres keeps every
# type it had — these are variants, not downgrades — and SQLite gets the
# nearest thing it can store.
#
# ``sqlalchemy.Uuid`` needs no help here and is used directly in the models: it
# already renders as ``UUID`` on Postgres and ``CHAR(32)`` on SQLite.
# ---------------------------------------------------------------------------


#: A JSON object. ``JSONB`` on Postgres, which is what these columns already
#: were; plain JSON text on SQLite.
Json = JSON().with_variant(JSONB(), "postgresql")


def string_array(length: int) -> TypeEngine[Any]:
    """An ordered list of short strings.

    A real ``VARCHAR[]`` on Postgres. SQLite has no array type, so there it is
    a JSON array — which needs no conversion either way, because a list of
    strings is already something ``json`` can represent.

    Nothing queries these with an array operator (``@>``, ``ANY``), only reads
    and writes them whole, so the two representations are interchangeable.
    """
    return ARRAY(String(length)).with_variant(JSON(), "sqlite")


class UuidArray(TypeDecorator[list[uuid.UUID]]):
    """An ordered list of UUIDs naming rows in another table.

    The same idea as :func:`string_array`, but it cannot be a plain variant:
    ``json`` refuses a ``uuid.UUID``, so on SQLite the values have to become
    strings on the way down and UUIDs again on the way up. Postgres stores them
    as the ``UUID[]`` it always did and skips both steps.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(Uuid()))
        return dialect.type_descriptor(JSON())

    def process_bind_param(
        self, value: list[uuid.UUID] | None, dialect: Dialect
    ) -> list[Any] | None:
        if value is None or dialect.name == "postgresql":
            return value
        return [str(item) for item in value]

    def process_result_value(
        self, value: list[Any] | None, dialect: Dialect
    ) -> list[uuid.UUID] | None:
        if value is None or dialect.name == "postgresql":
            return value
        return [
            item if isinstance(item, uuid.UUID) else uuid.UUID(item) for item in value
        ]


class UtcDateTime(TypeDecorator[datetime]):
    """A timestamp that comes back timezone-aware UTC from either database.

    Postgres has ``TIMESTAMPTZ`` and returns an aware datetime by itself.
    SQLite has no notion of a timezone: it stores the string it is handed and
    gives back a naive datetime, so an aware value bound to it would quietly
    lose its offset — the kind of difference that surfaces much later as
    timestamps sorting wrongly between a synced desktop and the server.

    Both ends are therefore pinned here: anything aware is converted to UTC
    before it is stored, and everything read back is stamped as UTC. The
    ``func.now()`` defaults below are already UTC on both, SQLite's
    ``CURRENT_TIMESTAMP`` being documented as such, so a row the database
    timestamped itself needs nothing done to it.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None or dialect.name == "postgresql" or value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def prepare_sqlite(engine: Engine) -> Engine:
    """Make a SQLite engine behave the way the rest of the app assumes.

    Two things are off by default and both matter here.

    SQLite does not enforce ``ON DELETE CASCADE`` unless foreign keys are
    switched on per connection. Every section table cascades from ``users``,
    and the routers rely on that, so without this a local delete would leave
    orphaned rows behind where the hosted database has none.

    The driver also opens its own transactions at times of its choosing, which
    breaks ``SAVEPOINT`` — the mechanism the tests use to roll back an
    endpoint's own ``commit()``. Taking that over, as SQLAlchemy's own
    documentation for pysqlite recommends, hands transaction control back to
    SQLAlchemy.

    A no-op on any other dialect, so it is safe to call on whatever engine the
    settings produced.
    """
    if engine.dialect.name != "sqlite":
        return engine

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
        # stop pysqlite emitting its own BEGIN
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(connection: Any) -> None:
        connection.exec_driver_sql("BEGIN")

    return engine

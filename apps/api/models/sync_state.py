"""What a local database remembers about the account it syncs with.

None of this is meaningful on the server. It is the desktop's side of the
conversation: where it has got to in the account's history, where the account
has got to in its own, and — per record — the last version the two sides agreed
about. That last part is what makes conflict detection possible in both
directions rather than just one.
"""

import uuid
from typing import Any

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, Json, enum_values
from enums import SectionType


class SyncState(Base):
    """The one row describing this database's relationship with an account.

    Absent until somebody signs in, which is also how "is this library
    connected to anything" is answered.
    """

    __tablename__ = "sync_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, unique=True
    )

    account_email: Mapped[str] = mapped_column(String(255), nullable=False)

    #: Where the account lives. Stored rather than compiled in so a build can
    #: be pointed at a staging deployment, and so an installed app does not
    #: have to be replaced to follow the service moving.
    cloud_base_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    # The session this database uses to reach the account. It sits beside the
    # data it protects: anyone who can read this file can already read every
    # resume in it, so keeping the token elsewhere would guard the door of a
    # house with no walls.
    access_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    #: The account's ``seq`` this database has caught up to.
    cloud_cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: This database's own ``seq`` that the account has been told about.
    local_cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SyncAgreement(Base):
    """The last version of one record that both sides were known to share.

    Two numbers because each side counts its own history. Comparing a side's
    current version against the one recorded here is what says "this side has
    changed since we last agreed" — and when both have, that is a conflict.
    """

    __tablename__ = "sync_agreements"
    __table_args__ = (
        UniqueConstraint("user_id", "record_id", name="uq_sync_agreements_record"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    record_type: Mapped[SectionType] = mapped_column(
        SQLEnum(SectionType, name="section_version_type", values_callable=enum_values),
        nullable=False,
    )

    local_version: Mapped[int] = mapped_column(Integer, nullable=False)
    cloud_version: Mapped[int] = mapped_column(Integer, nullable=False)


class SyncConflict(Base):
    """A record both sides changed, waiting for a person to say which they meant.

    Kept rather than resolved, because there is no rule that gets this right:
    the newer edit is not the better one, and quietly picking either is how a
    sync loses work. Both snapshots are stored so the choice can be shown long
    after the sync that found it.
    """

    __tablename__ = "sync_conflicts"
    __table_args__ = (
        UniqueConstraint("user_id", "record_id", name="uq_sync_conflicts_record"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    record_type: Mapped[SectionType] = mapped_column(
        SQLEnum(SectionType, name="section_version_type", values_callable=enum_values),
        nullable=False,
    )

    local_version: Mapped[int] = mapped_column(Integer, nullable=False)
    cloud_version: Mapped[int] = mapped_column(Integer, nullable=False)

    local_snapshot: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False)
    cloud_snapshot: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False)

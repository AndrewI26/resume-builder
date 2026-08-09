import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.oauth_account import OAuthAccount


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # display name; only OAuth providers supply one today, so it stays null for
    # accounts created through /auth/register
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # null for users who only ever signed in through an OAuth provider
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

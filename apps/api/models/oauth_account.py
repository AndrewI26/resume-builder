import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.user import User

GOOGLE_PROVIDER = "google"


class OAuthAccount(Base):
    """A third party identity (currently only Google) linked to a local user."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_accounts_provider_account"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # the provider's own stable id for the account (Google's `sub` claim)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # the email the provider reported at link time, kept for support/debugging
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(back_populates="oauth_accounts")

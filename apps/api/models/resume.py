import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Resume(Base):
    """One rendered document: which sections appear, in what order, under what name.

    A resume owns no section content of its own. Sections stay attached to the
    user so one experience can appear in several resume variants, and
    ``resume_sections`` records the membership.
    """

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(50), nullable=False, default="jakes")

    # the name printed across the top. Null falls back to ``User.name``, which
    # is itself null for accounts that never signed in through a provider.
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # nulled rather than cascaded, so deleting a contact block leaves the
    # resume intact and merely headerless
    personal_info_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("personal_info.id", ondelete="SET NULL"), nullable=True
    )

    # the order section headings are laid out in, as ``ResumeSectionType``
    # values. A type left out of this list is not rendered at all, which is how
    # a section is hidden without being detached.
    section_order: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, default=list
    )

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class BulletPoint(Base):
    __tablename__ = "bullet_points"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    text: Mapped[str] = mapped_column(String, nullable=False)
    bolded: Mapped[list[list[int]]] = mapped_column(JSONB, default=list)

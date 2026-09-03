import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, Json


class BulletPoint(Base):
    __tablename__ = "bullet_points"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    text: Mapped[str] = mapped_column(String, nullable=False)
    bolded: Mapped[list[list[int]]] = mapped_column(Json, default=list)

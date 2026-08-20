from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.bullet_point import BulletPoint

Technology = Annotated[str, Field(max_length=255)]


class ProjectCreate(BaseModel):
    name: str = Field(max_length=255)
    link: str | None = Field(default=None, max_length=2048)

    technologies: list[Technology]
    bullet_points: list[BulletPoint]


class ProjectRead(ProjectCreate):
    id: UUID

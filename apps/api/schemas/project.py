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


class ProjectEdit(BaseModel):
    id: UUID

    name: str | None = Field(default=None, max_length=255)
    # Deliberately not nullable: send a string to change the link, or leave the
    # field out to keep the current one. An explicit null is rejected.
    #
    # The `str` annotation is what makes null a validation error and keeps the
    # OpenAPI schema non-nullable. The None default is never validated (and is
    # dropped by `exclude_unset`), so it only marks the field as optional.
    link: str = Field(default=None, max_length=2048)  # type: ignore[assignment]

    technologies: list[Technology] | None = None
    bullet_points: list[BulletPoint] | None = None


class ProjectDelete(BaseModel):
    id: UUID

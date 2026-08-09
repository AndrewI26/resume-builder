from uuid import UUID

from pydantic import BaseModel, Field

from schemas.bullet_point import BulletPoint


class ExpirenceCreate(BaseModel):
    company: str = Field(max_length=255)
    position: str = Field(max_length=255)

    duration: str = Field(max_length=255)
    location: str = Field(max_length=255)

    bullet_points: list[BulletPoint]


class ExpirenceRead(ExpirenceCreate):
    id: UUID


class ExpirenceEdit(BaseModel):
    company: str | None = Field(default=None, max_length=255)
    position: str | None = Field(default=None, max_length=255)

    duration: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)

    bullet_points: list[BulletPoint] | None = None

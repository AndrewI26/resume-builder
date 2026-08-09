from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.fields import omittable, omittable_str

SkillItem = Annotated[str, Field(max_length=255)]


class SkillCreate(BaseModel):
    name: str = Field(max_length=255)
    items: list[SkillItem]

    # Left out means "append after the caller's existing lists".
    position: int | None = Field(default=None, ge=0)


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    name: str
    items: list[str]
    position: int


class SkillEdit(BaseModel):
    # All three columns are NOT NULL, so a field is either a value or left out
    # entirely. See `schemas.fields.omittable`.
    name: str = omittable_str(255)
    items: list[SkillItem] = omittable()
    position: int = omittable(ge=0)

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    """The full representation a replace has to send.

    Unlike `SkillCreate`, `position` is required: there is no list to append
    after, only an existing one whose place the caller has to state.
    """

    name: str = Field(max_length=255)
    items: list[SkillItem]
    position: int = Field(ge=0)

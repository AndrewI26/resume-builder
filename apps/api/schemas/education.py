from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Course = Annotated[str, Field(max_length=255)]


class EducationCreate(BaseModel):
    name: str = Field(max_length=255)
    subheading: str = Field(max_length=255)

    duration: str = Field(max_length=255)
    location: str = Field(max_length=255)

    # optional: an education with none simply has no coursework line
    coursework: list[Course] = Field(default=[], max_length=100)


class EducationRead(EducationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

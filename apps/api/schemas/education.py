from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EducationCreate(BaseModel):
    name: str = Field(max_length=255)
    subheading: str = Field(max_length=255)

    duration: str = Field(max_length=255)
    location: str = Field(max_length=255)


class EducationRead(EducationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

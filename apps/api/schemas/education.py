from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.fields import omittable_str


class EducationCreate(BaseModel):
    name: str = Field(max_length=255)
    subheading: str = Field(max_length=255)

    duration: str = Field(max_length=255)
    location: str = Field(max_length=255)


class EducationRead(EducationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class EducationEdit(BaseModel):
    # Every column behind these is NOT NULL, so a field is either a string or
    # left out entirely. See `schemas.fields.omittable_str`.
    name: str = omittable_str(255)
    subheading: str = omittable_str(255)

    duration: str = omittable_str(255)
    location: str = omittable_str(255)

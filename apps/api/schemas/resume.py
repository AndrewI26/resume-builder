from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResumeCreate(BaseModel):
    name: str = Field(max_length=255)
    sections: list[UUID] = []


class ResumeRead(ResumeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    updated_at: datetime


class ResumeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    sections: list[UUID] | None = None

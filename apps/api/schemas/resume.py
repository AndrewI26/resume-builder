from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResumeCreate(BaseModel):
    name: str
    sections: list[UUID] = []


class ResumeRead(ResumeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class ResumeUpdate(BaseModel):
    name: str | None = None
    sections: list[UUID] | None = None

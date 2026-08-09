from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonalInfoBase(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)

    github: str | None = Field(default=None, max_length=2048)
    linkedin: str | None = Field(default=None, max_length=2048)
    portfolio: str | None = Field(default=None, max_length=2048)


class PersonalInfoCreate(PersonalInfoBase):
    """Every field is optional; omitting one leaves it unset."""


class PersonalInfoRead(PersonalInfoBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class PersonalInfoEdit(PersonalInfoBase):
    """Partial update.

    Unlike the other resume tables, these columns are all nullable, so null is
    a meaningful value here: omit a field to leave it alone, or send null to
    clear it.
    """

    id: UUID


class PersonalInfoDelete(BaseModel):
    id: UUID

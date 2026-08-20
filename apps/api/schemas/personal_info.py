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
    """The full representation, used to create a row and to replace one.

    Every field is optional, so on a create an omitted field is stored as null
    and on a replace it clears whatever was there.
    """


class PersonalInfoRead(PersonalInfoBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

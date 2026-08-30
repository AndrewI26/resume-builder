from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.link import Link


class PersonalInfoBase(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)

    github: Link | None = None
    linkedin: Link | None = None
    portfolio: Link | None = None


class PersonalInfoCreate(PersonalInfoBase):
    """The full representation, used to create a row and to replace one.

    Every field is optional, so on a create an omitted field is stored as null
    and on a replace it clears whatever was there.
    """


class PersonalInfoRead(PersonalInfoBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

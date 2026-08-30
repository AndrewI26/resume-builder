from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleCredential(BaseModel):
    """The ID token Google Identity Services hands the frontend."""

    credential: str


class UserUpdate(BaseModel):
    """The parts of a profile its owner may change."""

    # an empty submission clears the name rather than storing ""
    name: str | None = Field(default=None, max_length=255)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str | None
    created_at: datetime
    # "password" and/or an OAuth provider name, e.g. "google"
    sign_in_methods: list[str]

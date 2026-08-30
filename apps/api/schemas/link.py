from pydantic import BaseModel, Field


class Link(BaseModel):
    """A URL paired with the text a resume shows in its place.

    `label` is optional: a caller that only has the URL can omit it, and the
    renderer falls back to showing the URL itself.
    """

    url: str = Field(max_length=2048)
    label: str | None = Field(default=None, max_length=255)

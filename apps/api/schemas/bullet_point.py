from pydantic import BaseModel, ValidationInfo, field_validator


class BulletPoint(BaseModel):
    """A line of resume text plus the runs of it that render bold.

    Each range in ``bolded`` is a pair of **inclusive** character indices into
    ``text``: ``(0, 6)`` over ``"Shipped it"`` bolds ``"Shipped"``. Ranges must
    arrive sorted and disjoint, so a renderer can walk them in one pass and
    cannot be handed overlaps that would nest one bold inside another.
    """

    text: str
    bolded: list[tuple[int, int]]

    @field_validator("bolded")
    @classmethod
    def validate_bolded(cls, bolded: list[tuple[int, int]], info: ValidationInfo):
        # a failed `text` validation leaves it absent, and there is nothing to
        # check offsets against
        text = info.data.get("text")
        if text is None:
            return bolded

        previous_end: int | None = None

        for start, end in bolded:
            if start > end:
                raise ValueError("Start must be less than or equal to end")

            if start < 0 or end < 0:
                raise ValueError("Coordinates must be >= 0")

            if start >= len(text) or end >= len(text):
                raise ValueError(f"Coordinates must be less than {len(text)}")

            if previous_end is not None and start <= previous_end:
                raise ValueError("Ranges must be sorted and must not overlap")

            previous_end = end

        return bolded

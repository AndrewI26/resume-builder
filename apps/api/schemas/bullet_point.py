from pydantic import BaseModel, ValidationInfo, field_validator


class BulletPoint(BaseModel):
    text: str
    bolded: list[tuple[int, int]]

    @field_validator("bolded")
    @classmethod
    def validate_bolded(cls, bolded: list[tuple[int, int]], info: ValidationInfo):
        text = info.data["text"]

        for start, end in bolded:
            if start > end:
                raise ValueError("First value must be less than the second")

            if start > end:
                raise ValueError("Start must be less than or equal to end")

            if start < 0 or end < 0:
                raise ValueError("Coordinates must be >= 0")

            if start >= len(text) or end >= len(text):
                raise ValueError(f"Coordinates must be less than {len(text)}")

        return bolded

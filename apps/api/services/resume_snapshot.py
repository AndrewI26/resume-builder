"""What a resume looks like, for the history.

A resume is its own fields plus the sections it has chosen, and the two are
edited through different endpoints but are one thing to a person: "my backend
resume" is the title and the list together. The snapshot holds both so that one
entry in the history describes the whole resume as it stood, and restoring or
comparing one never has to reassemble it from two places.

The membership rows carry no content — they point at sections that have their
own history — so this stays small no matter how much is in the library.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.resume import Resume
from models.resume_section import ResumeSection
from schemas.resume import ResumeRead


def section_refs(db: Session, resume_id: Any) -> list[dict[str, Any]]:
    """A resume's membership list, in the order it is rendered."""
    rows = db.scalars(
        select(ResumeSection)
        .where(ResumeSection.resume_id == resume_id)
        .order_by(ResumeSection.section_type, ResumeSection.position)
    ).all()

    return [
        {
            "section_type": row.section_type.value,
            "section_id": str(row.section_id),
            "position": row.position,
        }
        for row in rows
    ]


def resume_snapshot(resume: Resume, sections: list[dict[str, Any]]) -> dict[str, Any]:
    """The resume as the history records it.

    ``sections`` is passed in rather than read here because a delete has to
    capture them before the rows cascade away.
    """
    return {
        **ResumeRead.model_validate(resume).model_dump(mode="json"),
        "sections": sections,
    }

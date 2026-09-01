from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.section_version import SectionVersion


def record_version(
    db: Session,
    user_id: UUID,
    section_type: SectionType,
    section_id: UUID,
    operation: OperationType,
    snapshot: dict[str, Any],
) -> None:
    stmt = select(func.max(SectionVersion.version)).where(
        SectionVersion.section_id == section_id
    )
    latest_version = db.scalar(stmt)

    section_version = SectionVersion(
        user_id=user_id,
        section_type=section_type,
        section_id=section_id,
        version=(latest_version or 0) + 1,
        operation=operation,
        snapshot=snapshot,
    )

    db.add(section_version)
    db.commit()

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from enums import OperationType, SectionType


def record_version(
    db: Session,
    user_id: UUID,
    section_type: SectionType,
    section_id: UUID,
    operation: OperationType,
    snapshot: dict[str, Any],
):
    pass

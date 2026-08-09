"""Shared helpers for the bullet points referenced by experiences and projects.

Both tables store bullet points as an array of ids rather than a relationship,
so the rows have to be inserted, hydrated and cleaned up by hand.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from models.bullet_points import BulletPoint as BulletPointModel
from schemas.bullet_point import BulletPoint


def insert_bullet_points(
    db: Session, bullet_points: Sequence[BulletPoint]
) -> list[UUID]:
    """Insert bullet point rows and return their ids, in payload order."""
    if not bullet_points:
        return []

    stmt = insert(BulletPointModel).returning(
        BulletPointModel.id, sort_by_parameter_order=True
    )
    params = [
        {"text": bullet.text, "bolded": [[start, end] for start, end in bullet.bolded]}
        for bullet in bullet_points
    ]
    return list(db.scalars(stmt, params))


def delete_bullet_points(db: Session, ids: Sequence[UUID]) -> None:
    if not ids:
        return

    db.execute(delete(BulletPointModel).where(BulletPointModel.id.in_(set(ids))))


def bullet_points_by_id(db: Session, ids: Sequence[UUID]) -> dict[UUID, BulletPoint]:
    if not ids:
        return {}

    stmt = select(BulletPointModel).where(BulletPointModel.id.in_(set(ids)))
    return {
        row.id: BulletPoint(
            text=row.text, bolded=[(start, end) for start, end in row.bolded]
        )
        for row in db.scalars(stmt)
    }


def hydrate(ids: Sequence[UUID], by_id: dict[UUID, BulletPoint]) -> list[BulletPoint]:
    """Resolve stored ids to bullet points, preserving the stored order."""
    return [by_id[bullet_id] for bullet_id in ids if bullet_id in by_id]

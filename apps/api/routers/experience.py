from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from models.expirence import Expirence
from schemas.bullet_point import BulletPoint
from schemas.expirence import (
    ExpirenceCreate,
    ExpirenceDelete,
    ExpirenceEdit,
    ExpirenceRead,
)
from services.bullet_points import (
    bullet_points_by_id,
    delete_bullet_points,
    hydrate,
    insert_bullet_points,
)

router = APIRouter(prefix="/experience", tags=["Experience"])


def _to_read(expirence: Expirence, by_id: dict[UUID, BulletPoint]) -> ExpirenceRead:
    """Rebuild an experience with its bullet points hydrated, in stored order."""
    return ExpirenceRead(
        id=expirence.id,
        company=expirence.company,
        position=expirence.position,
        duration=expirence.duration,
        location=expirence.location,
        bullet_points=hydrate(expirence.bullet_points, by_id),
    )


@router.get("/", response_model=list[ExpirenceRead])
def get_experience(current_user: CurrentUser, db: Db):
    stmt = select(Expirence).where(Expirence.user_id == current_user.id)
    expirences = db.scalars(stmt).all()

    by_id = bullet_points_by_id(
        db, [bullet_id for row in expirences for bullet_id in row.bullet_points]
    )
    return [_to_read(row, by_id) for row in expirences]


@router.post("/", response_model=ExpirenceRead, status_code=status.HTTP_201_CREATED)
def create_experience(expirence: ExpirenceCreate, current_user: CurrentUser, db: Db):
    bullet_ids = insert_bullet_points(db, expirence.bullet_points)

    stmt = (
        insert(Expirence)
        .values(
            user_id=current_user.id,
            company=expirence.company,
            position=expirence.position,
            duration=expirence.duration,
            location=expirence.location,
            bullet_points=bullet_ids,
        )
        .returning(Expirence)
    )
    new_expirence = db.scalars(stmt).one()

    result = _to_read(new_expirence, bullet_points_by_id(db, bullet_ids))
    db.commit()

    return result


@router.put("/", response_model=ExpirenceRead)
def edit_expirence(expirence: ExpirenceEdit, current_user: CurrentUser, db: Db):
    values = expirence.model_dump(exclude_unset=True, exclude={"id", "bullet_points"})

    stale_bullet_ids: list[UUID] = []
    if expirence.bullet_points is not None:
        stale_bullet_ids = list(
            db.scalars(
                select(Expirence.bullet_points).where(
                    Expirence.id == expirence.id,
                    Expirence.user_id == current_user.id,
                )
            ).one_or_none()
            or []
        )
        values["bullet_points"] = insert_bullet_points(db, expirence.bullet_points)

    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    stmt = (
        update(Expirence)
        .where(Expirence.id == expirence.id, Expirence.user_id == current_user.id)
        .values(**values)
        .returning(Expirence)
    )
    edited_expirence = db.scalars(stmt).one_or_none()
    if edited_expirence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    delete_bullet_points(db, stale_bullet_ids)

    result = _to_read(
        edited_expirence, bullet_points_by_id(db, edited_expirence.bullet_points)
    )
    db.commit()

    return result


@router.delete("/", response_model=ExpirenceRead)
def delete_expirence(expirence: ExpirenceDelete, current_user: CurrentUser, db: Db):
    stmt = (
        delete(Expirence)
        .where(Expirence.id == expirence.id, Expirence.user_id == current_user.id)
        .returning(Expirence)
    )
    deleted_expirence = db.scalars(stmt).one_or_none()
    if deleted_expirence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    bullet_ids = list(deleted_expirence.bullet_points)
    result = _to_read(deleted_expirence, bullet_points_by_id(db, bullet_ids))

    delete_bullet_points(db, bullet_ids)
    db.commit()

    return result

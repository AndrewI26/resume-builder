from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from enums import OperationType, ResumeSectionType, SectionType
from models.expirence import Expirence
from schemas.expirence import ExpirenceCreate, ExpirenceRead
from services.bullet_points import (
    bullet_points_by_id,
    delete_bullet_points,
    insert_bullet_points,
)
from services.record_section import record_version
from services.resume_sections import detach_section
from services.sections import expirence_to_read as _to_read

router = APIRouter(prefix="/experience", tags=["Experience"])


@router.get("/", response_model=list[ExpirenceRead])
def get_experiences(current_user: CurrentUser, db: Db) -> list[ExpirenceRead]:
    stmt = select(Expirence).where(Expirence.user_id == current_user.id)
    expirences = db.scalars(stmt).all()

    by_id = bullet_points_by_id(
        db, [bullet_id for row in expirences for bullet_id in row.bullet_points]
    )
    return [_to_read(row, by_id) for row in expirences]


@router.get("/{expirence_id}", response_model=ExpirenceRead)
def get_experience(
    expirence_id: UUID, current_user: CurrentUser, db: Db
) -> ExpirenceRead:
    stmt = select(Expirence).where(
        Expirence.id == expirence_id, Expirence.user_id == current_user.id
    )
    expirence = db.scalars(stmt).one_or_none()
    if expirence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return _to_read(expirence, bullet_points_by_id(db, expirence.bullet_points))


@router.post("/", response_model=ExpirenceRead, status_code=status.HTTP_201_CREATED)
def create_experience(
    expirence: ExpirenceCreate, current_user: CurrentUser, db: Db
) -> ExpirenceRead:
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

    record_version(
        db,
        current_user.id,
        SectionType.EXPERIENCE,
        new_expirence.id,
        OperationType.CREATE,
        result.model_dump(mode="json"),
    )

    return result


@router.put("/{expirence_id}", response_model=ExpirenceRead)
def edit_expirence(
    expirence_id: UUID, expirence: ExpirenceCreate, current_user: CurrentUser, db: Db
) -> ExpirenceRead:
    stale_bullet_ids = list(
        db.scalars(
            select(Expirence.bullet_points).where(
                Expirence.id == expirence_id,
                Expirence.user_id == current_user.id,
            )
        ).one_or_none()
        or []
    )

    stmt = (
        update(Expirence)
        .where(Expirence.id == expirence_id, Expirence.user_id == current_user.id)
        .values(
            company=expirence.company,
            position=expirence.position,
            duration=expirence.duration,
            location=expirence.location,
            bullet_points=insert_bullet_points(db, expirence.bullet_points),
        )
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

    record_version(
        db,
        current_user.id,
        SectionType.EXPERIENCE,
        expirence_id,
        OperationType.UPDATE,
        result.model_dump(mode="json"),
    )

    return result


@router.delete("/{expirence_id}", response_model=ExpirenceRead)
def delete_expirence(
    expirence_id: UUID, current_user: CurrentUser, db: Db
) -> ExpirenceRead:
    stmt = (
        delete(Expirence)
        .where(Expirence.id == expirence_id, Expirence.user_id == current_user.id)
        .returning(Expirence)
    )
    deleted_expirence = db.scalars(stmt).one_or_none()
    if deleted_expirence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    bullet_ids = list(deleted_expirence.bullet_points)
    result = _to_read(deleted_expirence, bullet_points_by_id(db, bullet_ids))

    delete_bullet_points(db, bullet_ids)
    detach_section(db, ResumeSectionType.EXPERIENCE, expirence_id)
    db.commit()

    record_version(
        db,
        current_user.id,
        SectionType.EXPERIENCE,
        expirence_id,
        OperationType.DELETE,
        result.model_dump(mode="json"),
    )

    return result

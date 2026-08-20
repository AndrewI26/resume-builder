from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from enums import OperationType, SectionType
from models.education import Education
from schemas.education import (
    EducationCreate,
    EducationEdit,
    EducationRead,
)
from services.record_section import record_version

router = APIRouter(prefix="/education", tags=["Education"])


@router.get("/", response_model=list[EducationRead])
def get_educations(current_user: CurrentUser, db: Db):
    stmt = select(Education).where(Education.user_id == current_user.id)
    return db.scalars(stmt).all()


@router.get("/{education_id}", response_model=EducationRead)
def get_education(education_id: UUID, current_user: CurrentUser, db: Db):
    stmt = select(Education).where(
        Education.id == education_id, Education.user_id == current_user.id
    )
    education = db.scalars(stmt).one_or_none()
    if education is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return education


@router.post("/", response_model=EducationRead, status_code=status.HTTP_201_CREATED)
def create_education(education: EducationCreate, current_user: CurrentUser, db: Db):
    stmt = (
        insert(Education)
        .values(
            user_id=current_user.id,
            name=education.name,
            subheading=education.subheading,
            duration=education.duration,
            location=education.location,
        )
        .returning(Education)
    )
    new_education = db.scalars(stmt).one()

    result = EducationRead.model_validate(new_education)

    record_version(
        db,
        current_user.id,
        SectionType.EDUCATION,
        new_education.id,
        OperationType.CREATE,
        result.model_dump(mode="json"),
    )

    return result


@router.put("/{education_id}", response_model=EducationRead)
def edit_education(
    education_id: UUID, education: EducationEdit, current_user: CurrentUser, db: Db
):
    values = education.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    stmt = (
        update(Education)
        .where(Education.id == education_id, Education.user_id == current_user.id)
        .values(**values)
        .returning(Education)
    )
    edited_education = db.scalars(stmt).one_or_none()
    if edited_education is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = EducationRead.model_validate(edited_education)
    db.commit()

    return result


@router.delete("/{education_id}", response_model=EducationRead)
def delete_education(education_id: UUID, current_user: CurrentUser, db: Db):
    stmt = (
        delete(Education)
        .where(Education.id == education_id, Education.user_id == current_user.id)
        .returning(Education)
    )
    deleted_education = db.scalars(stmt).one_or_none()
    if deleted_education is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = EducationRead.model_validate(deleted_education)
    db.commit()

    return result

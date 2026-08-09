from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from models.education import Education
from schemas.education import (
    EducationCreate,
    EducationDelete,
    EducationEdit,
    EducationRead,
)

router = APIRouter(prefix="/education", tags=["Education"])


@router.get("/", response_model=list[EducationRead])
def get_educations(current_user: CurrentUser, db: Db):
    stmt = select(Education).where(Education.user_id == current_user.id)
    return db.scalars(stmt).all()


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
    db.commit()

    return result


@router.put("/", response_model=EducationRead)
def edit_education(education: EducationEdit, current_user: CurrentUser, db: Db):
    values = education.model_dump(exclude_unset=True, exclude={"id"})
    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    stmt = (
        update(Education)
        .where(Education.id == education.id, Education.user_id == current_user.id)
        .values(**values)
        .returning(Education)
    )
    edited_education = db.scalars(stmt).one_or_none()
    if edited_education is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = EducationRead.model_validate(edited_education)
    db.commit()

    return result


@router.delete("/", response_model=EducationRead)
def delete_education(education: EducationDelete, current_user: CurrentUser, db: Db):
    stmt = (
        delete(Education)
        .where(Education.id == education.id, Education.user_id == current_user.id)
        .returning(Education)
    )
    deleted_education = db.scalars(stmt).one_or_none()
    if deleted_education is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = EducationRead.model_validate(deleted_education)
    db.commit()

    return result

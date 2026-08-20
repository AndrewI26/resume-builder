from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from enums import OperationType, SectionType
from models.personal_info import PersonalInfo
from schemas.personal_info import PersonalInfoCreate, PersonalInfoRead
from services.record_section import record_version

router = APIRouter(prefix="/personal-info", tags=["Personal info"])


@router.get("/", response_model=list[PersonalInfoRead])
def get_all_personal_info(current_user: CurrentUser, db: Db):
    stmt = select(PersonalInfo).where(PersonalInfo.user_id == current_user.id)
    return db.scalars(stmt).all()


@router.get("/{personal_info_id}", response_model=PersonalInfoRead)
def get_personal_info(personal_info_id: UUID, current_user: CurrentUser, db: Db):
    stmt = select(PersonalInfo).where(
        PersonalInfo.id == personal_info_id,
        PersonalInfo.user_id == current_user.id,
    )
    personal_info = db.scalars(stmt).one_or_none()
    if personal_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return personal_info


@router.post("/", response_model=PersonalInfoRead, status_code=status.HTTP_201_CREATED)
def create_personal_info(
    personal_info: PersonalInfoCreate, current_user: CurrentUser, db: Db
):
    stmt = (
        insert(PersonalInfo)
        .values(user_id=current_user.id, **personal_info.model_dump())
        .returning(PersonalInfo)
    )
    new_personal_info = db.scalars(stmt).one()

    result = PersonalInfoRead.model_validate(new_personal_info)

    record_version(
        db,
        current_user.id,
        SectionType.PERSONAL_INFO,
        new_personal_info.id,
        OperationType.CREATE,
        result.model_dump(mode="json"),
    )

    return result


@router.put("/{personal_info_id}", response_model=PersonalInfoRead)
def edit_personal_info(
    personal_info_id: UUID,
    personal_info: PersonalInfoCreate,
    current_user: CurrentUser,
    db: Db,
):
    stmt = (
        update(PersonalInfo)
        .where(
            PersonalInfo.id == personal_info_id,
            PersonalInfo.user_id == current_user.id,
        )
        .values(**personal_info.model_dump())
        .returning(PersonalInfo)
    )
    edited_personal_info = db.scalars(stmt).one_or_none()
    if edited_personal_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = PersonalInfoRead.model_validate(edited_personal_info)
    db.commit()

    return result


@router.delete("/{personal_info_id}", response_model=PersonalInfoRead)
def delete_personal_info(personal_info_id: UUID, current_user: CurrentUser, db: Db):
    stmt = (
        delete(PersonalInfo)
        .where(
            PersonalInfo.id == personal_info_id,
            PersonalInfo.user_id == current_user.id,
        )
        .returning(PersonalInfo)
    )
    deleted_personal_info = db.scalars(stmt).one_or_none()
    if deleted_personal_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = PersonalInfoRead.model_validate(deleted_personal_info)
    db.commit()

    return result

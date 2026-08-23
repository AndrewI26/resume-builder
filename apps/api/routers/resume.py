from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from models.resume import Resume
from schemas.resume import ResumeCreate, ResumeRead, ResumeUpdate

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("/", response_model=list[ResumeRead])
def get_resumes(db: Db, current_user: CurrentUser):
    stmt = select(Resume).where(Resume.user_id == current_user.id)
    return db.scalars(stmt).all()


@router.post("/", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def create_resume(resume: ResumeCreate, db: Db, current_user: CurrentUser):
    stmt = (
        insert(Resume)
        .values(
            user_id=current_user.id,
            name=resume.name,
            sections=resume.sections,
        )
        .returning(Resume)
    )
    new_resume = db.scalars(stmt).one()
    db.commit()

    return new_resume


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(resume_id: UUID, db: Db, current_user: CurrentUser):
    stmt = select(Resume).where(
        Resume.id == resume_id, Resume.user_id == current_user.id
    )
    resume = db.scalars(stmt).one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return resume


@router.patch("/{resume_id}", response_model=ResumeRead)
def update_resume(
    resume_id: UUID, resume: ResumeUpdate, db: Db, current_user: CurrentUser
):
    changes = resume.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    stmt = (
        update(Resume)
        .where(Resume.id == resume_id, Resume.user_id == current_user.id)
        .values(**changes)
        .returning(Resume)
    )
    updated_resume = db.scalars(stmt).one_or_none()
    if updated_resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    db.commit()

    return updated_resume


@router.delete("/{resume_id}", response_model=ResumeRead)
def delete_resume(resume_id: UUID, db: Db, current_user: CurrentUser):
    stmt = (
        delete(Resume)
        .where(Resume.id == resume_id, Resume.user_id == current_user.id)
        .returning(Resume)
    )
    deleted_resume = db.scalars(stmt).one_or_none()
    if deleted_resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    db.commit()

    return deleted_resume

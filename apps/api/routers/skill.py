from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from deps.auth import CurrentUser
from deps.db import Db
from models.skill import Skill
from schemas.skill import SkillCreate, SkillEdit, SkillRead

router = APIRouter(prefix="/skill", tags=["Skill"])


def _next_position(db: Session, user_id: UUID) -> int:
    """Append position: one past the caller's last list, or 0 if they have none."""
    highest = db.scalar(
        select(func.max(Skill.position)).where(Skill.user_id == user_id)
    )
    return 0 if highest is None else highest + 1


@router.get("/", response_model=list[SkillRead])
def get_skills(current_user: CurrentUser, db: Db):
    # created_at breaks ties: nothing stops two lists sharing a position.
    stmt = (
        select(Skill)
        .where(Skill.user_id == current_user.id)
        .order_by(Skill.position, Skill.created_at)
    )
    return db.scalars(stmt).all()


@router.get("/{skill_id}", response_model=SkillRead)
def get_skill(skill_id: UUID, current_user: CurrentUser, db: Db):
    stmt = select(Skill).where(Skill.id == skill_id, Skill.user_id == current_user.id)
    skill = db.scalars(stmt).one_or_none()
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return skill


@router.post("/", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
def create_skill(skill: SkillCreate, current_user: CurrentUser, db: Db):
    position = (
        _next_position(db, current_user.id)
        if skill.position is None
        else skill.position
    )

    stmt = (
        insert(Skill)
        .values(
            user_id=current_user.id,
            name=skill.name,
            items=skill.items,
            position=position,
        )
        .returning(Skill)
    )
    new_skill = db.scalars(stmt).one()

    result = SkillRead.model_validate(new_skill)
    db.commit()

    return result


@router.put("/{skill_id}", response_model=SkillRead)
def edit_skill(skill_id: UUID, skill: SkillEdit, current_user: CurrentUser, db: Db):
    values = skill.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    stmt = (
        update(Skill)
        .where(Skill.id == skill_id, Skill.user_id == current_user.id)
        .values(**values)
        .returning(Skill)
    )
    edited_skill = db.scalars(stmt).one_or_none()
    if edited_skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = SkillRead.model_validate(edited_skill)
    db.commit()

    return result


@router.delete("/{skill_id}", response_model=SkillRead)
def delete_skill(skill_id: UUID, current_user: CurrentUser, db: Db):
    stmt = (
        delete(Skill)
        .where(Skill.id == skill_id, Skill.user_id == current_user.id)
        .returning(Skill)
    )
    deleted_skill = db.scalars(stmt).one_or_none()
    if deleted_skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = SkillRead.model_validate(deleted_skill)
    db.commit()

    return result

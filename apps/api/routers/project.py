from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from models.project import Project
from schemas.bullet_point import BulletPoint
from schemas.project import (
    ProjectCreate,
    ProjectDelete,
    ProjectEdit,
    ProjectRead,
)
from services.bullet_points import (
    bullet_points_by_id,
    delete_bullet_points,
    hydrate,
    insert_bullet_points,
)

router = APIRouter(prefix="/project", tags=["Project"])


def _to_read(project: Project, by_id: dict[UUID, BulletPoint]) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        link=project.link,
        technologies=list(project.technologies),
        bullet_points=hydrate(project.bullet_points, by_id),
    )


@router.get("/", response_model=list[ProjectRead])
def get_projects(current_user: CurrentUser, db: Db):
    stmt = select(Project).where(Project.user_id == current_user.id)
    projects = db.scalars(stmt).all()

    by_id = bullet_points_by_id(
        db, [bullet_id for row in projects for bullet_id in row.bullet_points]
    )
    return [_to_read(row, by_id) for row in projects]


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, current_user: CurrentUser, db: Db):
    bullet_ids = insert_bullet_points(db, project.bullet_points)

    stmt = (
        insert(Project)
        .values(
            user_id=current_user.id,
            name=project.name,
            link=project.link,
            technologies=project.technologies,
            bullet_points=bullet_ids,
        )
        .returning(Project)
    )
    new_project = db.scalars(stmt).one()

    result = _to_read(new_project, bullet_points_by_id(db, bullet_ids))
    db.commit()

    return result


@router.put("/", response_model=ProjectRead)
def edit_project(project: ProjectEdit, current_user: CurrentUser, db: Db):
    values = project.model_dump(exclude_unset=True, exclude={"id", "bullet_points"})

    stale_bullet_ids: list[UUID] = []
    if project.bullet_points is not None:
        stale_bullet_ids = list(
            db.scalars(
                select(Project.bullet_points).where(
                    Project.id == project.id,
                    Project.user_id == current_user.id,
                )
            ).one_or_none()
            or []
        )
        values["bullet_points"] = insert_bullet_points(db, project.bullet_points)

    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    stmt = (
        update(Project)
        .where(Project.id == project.id, Project.user_id == current_user.id)
        .values(**values)
        .returning(Project)
    )
    edited_project = db.scalars(stmt).one_or_none()
    if edited_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    delete_bullet_points(db, stale_bullet_ids)

    result = _to_read(
        edited_project, bullet_points_by_id(db, edited_project.bullet_points)
    )
    db.commit()

    return result


@router.delete("/", response_model=ProjectRead)
def delete_project(project: ProjectDelete, current_user: CurrentUser, db: Db):
    stmt = (
        delete(Project)
        .where(Project.id == project.id, Project.user_id == current_user.id)
        .returning(Project)
    )
    deleted_project = db.scalars(stmt).one_or_none()
    if deleted_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    bullet_ids = list(deleted_project.bullet_points)
    result = _to_read(deleted_project, bullet_points_by_id(db, bullet_ids))

    delete_bullet_points(db, bullet_ids)
    db.commit()

    return result

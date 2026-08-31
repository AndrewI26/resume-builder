from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, insert, select, update

from deps.auth import CurrentUser
from deps.db import Db
from enums import OperationType, ResumeSectionType, SectionType
from models.project import Project
from schemas.project import ProjectCreate, ProjectRead
from services.bullet_points import (
    bullet_points_by_id,
    delete_bullet_points,
    insert_bullet_points,
)
from services.record_section import record_version
from services.resume_sections import detach_section
from services.sections import project_to_read as _to_read

router = APIRouter(prefix="/project", tags=["Project"])


@router.get("/", response_model=list[ProjectRead])
def get_projects(current_user: CurrentUser, db: Db) -> list[ProjectRead]:
    stmt = select(Project).where(Project.user_id == current_user.id)
    projects = db.scalars(stmt).all()

    by_id = bullet_points_by_id(
        db, [bullet_id for row in projects for bullet_id in row.bullet_points]
    )
    return [_to_read(row, by_id) for row in projects]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, current_user: CurrentUser, db: Db) -> ProjectRead:
    stmt = select(Project).where(
        Project.id == project_id, Project.user_id == current_user.id
    )
    project = db.scalars(stmt).one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return _to_read(project, bullet_points_by_id(db, project.bullet_points))


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate, current_user: CurrentUser, db: Db
) -> ProjectRead:
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

    record_version(
        db,
        current_user.id,
        SectionType.PROJECT,
        new_project.id,
        OperationType.CREATE,
        result.model_dump(mode="json"),
    )

    return result


@router.put("/{project_id}", response_model=ProjectRead)
def edit_project(
    project_id: UUID, project: ProjectCreate, current_user: CurrentUser, db: Db
) -> ProjectRead:
    stale_bullet_ids = list(
        db.scalars(
            select(Project.bullet_points).where(
                Project.id == project_id,
                Project.user_id == current_user.id,
            )
        ).one_or_none()
        or []
    )

    stmt = (
        update(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .values(
            name=project.name,
            link=project.link,
            technologies=project.technologies,
            bullet_points=insert_bullet_points(db, project.bullet_points),
        )
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


@router.delete("/{project_id}", response_model=ProjectRead)
def delete_project(project_id: UUID, current_user: CurrentUser, db: Db) -> ProjectRead:
    stmt = (
        delete(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .returning(Project)
    )
    deleted_project = db.scalars(stmt).one_or_none()
    if deleted_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    bullet_ids = list(deleted_project.bullet_points)
    result = _to_read(deleted_project, bullet_points_by_id(db, bullet_ids))

    delete_bullet_points(db, bullet_ids)
    detach_section(db, ResumeSectionType.PROJECT, project_id)
    db.commit()

    return result

"""Builders that turn a section row into its read schema.

Experiences and projects store bullet points as an array of ids, so rebuilding
one for a response takes a hydration step. Both the section's own router and
the resume document endpoint need that, which is why it lives here rather than
in either router.
"""

from uuid import UUID

from models.expirence import Expirence
from models.project import Project
from schemas.bullet_point import BulletPoint
from schemas.expirence import ExpirenceRead
from schemas.project import ProjectRead
from services.bullet_points import hydrate


def expirence_to_read(
    expirence: Expirence, by_id: dict[UUID, BulletPoint]
) -> ExpirenceRead:
    """Rebuild an experience with its bullet points hydrated, in stored order."""
    return ExpirenceRead(
        id=expirence.id,
        company=expirence.company,
        position=expirence.position,
        duration=expirence.duration,
        location=expirence.location,
        bullet_points=hydrate(expirence.bullet_points, by_id),
    )


def project_to_read(project: Project, by_id: dict[UUID, BulletPoint]) -> ProjectRead:
    """Rebuild a project with its bullet points hydrated, in stored order."""
    return ProjectRead(
        id=project.id,
        name=project.name,
        link=project.link,
        technologies=list(project.technologies),
        bullet_points=hydrate(project.bullet_points, by_id),
    )

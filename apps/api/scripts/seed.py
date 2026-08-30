"""Reproducible sample data for local development.

Run with ``bun run db:seed`` (after ``bun run db:upgrade``). Every row it writes
has a deterministic id derived from :data:`SEED_NAMESPACE`, so re-running wipes
exactly the rows this script owns and reinserts them — anything you created by
hand survives.

The demo account's password is committed in plain sight, so the script refuses
to run outside development.
"""

import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import models.oauth_account  # noqa: F401  (maps User.oauth_accounts)
from enums import DEFAULT_SECTION_ORDER, ResumeSectionType
from models.bullet_points import BulletPoint
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.resume_section import ResumeSection
from models.skill import Skill
from models.user import User
from services.security import hash_password
from settings import get_settings

SEED_EMAIL = "demo@example.com"
SEED_PASSWORD = "demo1234"

# Any fixed constant works; it only has to stay stable so the ids stay stable.
SEED_NAMESPACE = uuid.UUID("6f1a5a5e-0000-4000-8000-000000000000")


def sid(key: str) -> uuid.UUID:
    """A stable id for a seed row, e.g. ``sid("experience:acme")``."""
    return uuid.uuid5(SEED_NAMESPACE, key)


def bold(text: str, phrase: str) -> list[list[int]]:
    """The bolded range covering ``phrase`` within ``text``.

    Ends are inclusive, matching ``schemas.bullet_point.BulletPoint``. Computed
    rather than hand-counted so the offsets cannot drift from the text.
    """
    start = text.index(phrase)
    return [[start, start + len(phrase) - 1]]


@dataclass(frozen=True)
class Bullet:
    text: str
    bold_phrase: str | None = None

    @property
    def bolded(self) -> list[list[int]]:
        if self.bold_phrase is None:
            return []

        return bold(self.text, self.bold_phrase)


@dataclass(frozen=True)
class EducationSeed:
    key: str
    name: str
    subheading: str
    duration: str
    location: str


@dataclass(frozen=True)
class ExperienceSeed:
    key: str
    company: str
    position: str
    duration: str
    location: str
    bullets: list[Bullet] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectSeed:
    key: str
    name: str
    link: str
    technologies: list[str] = field(default_factory=list)
    bullets: list[Bullet] = field(default_factory=list)


@dataclass(frozen=True)
class SkillSeed:
    key: str
    name: str
    items: list[str]
    position: int


@dataclass(frozen=True)
class ResumeSeed:
    key: str
    title: str
    full_name: str
    # education/experience/project/skill keys only, in section-type run order.
    # Personal info attaches via `Resume.personal_info_id`, not membership.
    sections: list[str]


# --- the sample data ---------------------------------------------------------

SEED_USER_ID = sid("user:demo")

PERSONAL_INFO_KEY = "personal_info:default"

EDUCATIONS = [
    EducationSeed(
        key="education:state-university",
        name="B.S. Computer Science",
        subheading="State University",
        duration="2016 – 2020",
        location="Boston, MA",
    ),
    EducationSeed(
        key="education:northside-college",
        name="M.S. Distributed Systems",
        subheading="Northside College",
        duration="2020 – 2022",
        location="Providence, RI",
    ),
]

EXPERIENCES = [
    ExperienceSeed(
        key="experience:acme",
        company="Acme Corp",
        position="Senior Software Engineer",
        duration="2022 – Present",
        location="Remote",
        bullets=[
            Bullet(
                "Cut p99 API latency by 40% by introducing a read-through cache",
                "p99 API latency by 40%",
            ),
            Bullet(
                "Led the migration of 12 services from REST to gRPC with zero downtime",
                "zero downtime",
            ),
            Bullet(
                "Mentored three junior engineers through their first on-call rotations"
            ),
        ],
    ),
    ExperienceSeed(
        key="experience:globex",
        company="Globex",
        position="Software Engineer",
        duration="2020 – 2022",
        location="Providence, RI",
        bullets=[
            Bullet(
                "Rebuilt the billing pipeline, removing a recurring class of rounding bugs",
                "billing pipeline",
            ),
            Bullet(
                "Added contract tests that caught 30+ breaking changes before release"
            ),
        ],
    ),
    ExperienceSeed(
        key="experience:initech",
        company="Initech",
        position="Software Engineering Intern",
        duration="Summer 2019",
        location="Boston, MA",
        bullets=[
            Bullet("Built an internal dashboard used daily by the support team"),
            Bullet(
                "Automated a manual release checklist, saving roughly 4 hours a week"
            ),
        ],
    ),
]

PROJECTS = [
    ProjectSeed(
        key="project:resume-builder",
        name="Resume Builder",
        link="https://github.com/demo-user/resume-builder",
        technologies=["React", "FastAPI", "Postgres", "TypeScript"],
        bullets=[
            Bullet(
                "Renders LaTeX-quality PDFs from structured resume sections",
                "LaTeX-quality PDFs",
            ),
            Bullet(
                "Supports per-resume section ordering and reusable section libraries"
            ),
        ],
    ),
    ProjectSeed(
        key="project:pathfinder",
        name="Pathfinder",
        link="https://github.com/demo-user/pathfinder",
        technologies=["Go", "Redis"],
        bullets=[
            Bullet("Visualises shortest-path algorithms over user-drawn mazes"),
            Bullet("Handles 10k-node graphs in the browser without dropping frames"),
        ],
    ),
]

SKILLS = [
    SkillSeed(
        key="skill:languages",
        name="Languages",
        items=["Python", "TypeScript", "Go", "SQL"],
        position=0,
    ),
    SkillSeed(
        key="skill:frameworks",
        name="Frameworks",
        items=["FastAPI", "React", "SQLAlchemy"],
        position=1,
    ),
    SkillSeed(
        key="skill:tools",
        name="Tools",
        items=["Docker", "Postgres", "Git", "Alembic"],
        position=2,
    ),
]

RESUMES = [
    ResumeSeed(
        key="resume:software-engineer",
        title="Software Engineer",
        full_name="Demo User",
        sections=[
            "education:state-university",
            "experience:acme",
            "experience:globex",
            "project:resume-builder",
            "skill:languages",
            "skill:frameworks",
        ],
    ),
    ResumeSeed(
        key="resume:backend-focused",
        title="Backend Focused",
        full_name="Demo User",
        sections=[
            "education:northside-college",
            "education:state-university",
            "experience:acme",
            "experience:initech",
            "skill:languages",
            "skill:tools",
        ],
    ),
]


def bullet_ids(owner_key: str, bullets: list[Bullet]) -> list[uuid.UUID]:
    return [sid(f"bullet:{owner_key}:{index}") for index in range(len(bullets))]


def _section_type(key: str) -> ResumeSectionType:
    """The section type a seed key belongs to, from its ``type:name`` prefix."""
    prefix = key.split(":", 1)[0]
    return ResumeSectionType(prefix)


def _resume_section_rows(resume_id: uuid.UUID, keys: list[str]) -> list[ResumeSection]:
    """Membership rows for a resume, positioned within each type's own run."""
    grouped: dict[ResumeSectionType, list[str]] = defaultdict(list)
    for key in keys:
        grouped[_section_type(key)].append(key)

    return [
        ResumeSection(
            resume_id=resume_id,
            section_type=section_type,
            section_id=sid(key),
            position=position,
        )
        for section_type, type_keys in grouped.items()
        for position, key in enumerate(type_keys)
    ]


def seeded_section_ids() -> list[uuid.UUID]:
    """Every section id this script owns.

    Derived from the data above rather than hand-listed, so the wipe can never
    fall out of step with the insert.
    """
    keys = (
        [PERSONAL_INFO_KEY]
        + [row.key for row in EDUCATIONS]
        + [row.key for row in EXPERIENCES]
        + [row.key for row in PROJECTS]
        + [row.key for row in SKILLS]
    )
    return [sid(key) for key in keys]


def seeded_bullet_ids() -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []

    for row in EXPERIENCES:
        ids.extend(bullet_ids(row.key, row.bullets))

    for project in PROJECTS:
        ids.extend(bullet_ids(project.key, project.bullets))

    return ids


def _check_dataset() -> None:
    """Fails at import on a bad literal, rather than part-way through the SQL."""
    bullets = [bullet for row in EXPERIENCES for bullet in row.bullets]
    bullets += [bullet for row in PROJECTS for bullet in row.bullets]

    for bullet in bullets:
        for start, end in bullet.bolded:
            assert 0 <= start <= end < len(bullet.text), (
                f"bad bolded range {(start, end)} for {bullet.text!r}"
            )

    section_ids = seeded_section_ids()
    all_ids = (
        section_ids
        + seeded_bullet_ids()
        + [SEED_USER_ID]
        + [sid(row.key) for row in RESUMES]
    )
    assert len(all_ids) == len(set(all_ids)), "seed ids collide"

    known = set(section_ids)
    for resume in RESUMES:
        for key in resume.sections:
            assert sid(key) in known, f"resume references unseeded section {key}"


_check_dataset()


# --- write -------------------------------------------------------------------


def wipe(db: Session) -> None:
    """Removes the rows this script owns, and only those."""
    section_ids = seeded_section_ids()

    # bullet_points has no user_id and nothing cascades to it, so it has to be
    # cleared explicitly. Include whatever the seeded sections currently point
    # at, not just our own ids, or a bullet added by hand to a seeded experience
    # is orphaned forever.
    stale_bullets = set(seeded_bullet_ids())
    for bullets in db.scalars(
        select(Expirence.bullet_points).where(Expirence.id.in_(section_ids))
    ):
        stale_bullets.update(bullets or [])

    for bullets in db.scalars(
        select(Project.bullet_points).where(Project.id.in_(section_ids))
    ):
        stale_bullets.update(bullets or [])

    db.execute(delete(BulletPoint).where(BulletPoint.id.in_(stale_bullets)))

    db.execute(delete(Resume).where(Resume.id.in_([sid(r.key) for r in RESUMES])))
    db.execute(delete(Skill).where(Skill.id.in_(section_ids)))
    db.execute(delete(Project).where(Project.id.in_(section_ids)))
    db.execute(delete(PersonalInfo).where(PersonalInfo.id.in_(section_ids)))
    db.execute(delete(Education).where(Education.id.in_(section_ids)))
    db.execute(delete(Expirence).where(Expirence.id.in_(section_ids)))

    # Cascades anything the fixed-id deletes above missed.
    db.execute(delete(User).where(User.id == SEED_USER_ID))


def insert_all(db: Session) -> None:
    db.add(
        User(
            id=SEED_USER_ID,
            email=SEED_EMAIL,
            name="Demo User",
            hashed_password=hash_password(SEED_PASSWORD),
        )
    )
    db.flush()

    db.add(
        PersonalInfo(
            id=sid(PERSONAL_INFO_KEY),
            user_id=SEED_USER_ID,
            email=SEED_EMAIL,
            phone_number="+1 (555) 010-1234",
            address="Boston, MA",
            github={"url": "https://github.com/demo-user", "label": None},
            linkedin={
                "url": "https://linkedin.com/in/demo-user",
                "label": "in/demo-user",
            },
            portfolio={"url": "https://demo-user.dev", "label": "Portfolio"},
        )
    )

    for education in EDUCATIONS:
        db.add(
            Education(
                id=sid(education.key),
                user_id=SEED_USER_ID,
                name=education.name,
                subheading=education.subheading,
                duration=education.duration,
                location=education.location,
            )
        )

    for experience in EXPERIENCES:
        ids = bullet_ids(experience.key, experience.bullets)
        add_bullets(db, ids, experience.bullets)

        db.add(
            Expirence(
                id=sid(experience.key),
                user_id=SEED_USER_ID,
                company=experience.company,
                position=experience.position,
                duration=experience.duration,
                location=experience.location,
                bullet_points=ids,
            )
        )

    for project in PROJECTS:
        ids = bullet_ids(project.key, project.bullets)
        add_bullets(db, ids, project.bullets)

        db.add(
            Project(
                id=sid(project.key),
                user_id=SEED_USER_ID,
                name=project.name,
                link=project.link,
                technologies=project.technologies,
                bullet_points=ids,
            )
        )

    for skill in SKILLS:
        db.add(
            Skill(
                id=sid(skill.key),
                user_id=SEED_USER_ID,
                name=skill.name,
                items=skill.items,
                position=skill.position,
            )
        )

    for resume in RESUMES:
        new_resume = Resume(
            id=sid(resume.key),
            user_id=SEED_USER_ID,
            title=resume.title,
            full_name=resume.full_name,
            personal_info_id=sid(PERSONAL_INFO_KEY),
            section_order=[
                section_type.value for section_type in DEFAULT_SECTION_ORDER
            ],
        )
        db.add(new_resume)
        db.flush()

        for row in _resume_section_rows(new_resume.id, resume.sections):
            db.add(row)


def add_bullets(db: Session, ids: list[uuid.UUID], bullets: list[Bullet]) -> None:
    for bullet_uuid, bullet in zip(ids, bullets, strict=True):
        db.add(BulletPoint(id=bullet_uuid, text=bullet.text, bolded=bullet.bolded))


def main() -> int:
    settings = get_settings()

    if settings.node_env != "development":
        print(
            f"refusing to seed: NODE_ENV is {settings.node_env!r}, not 'development'",
            file=sys.stderr,
        )
        return 1

    # Imported here so the guard above runs before we try to connect: deps.db
    # builds its engine at import time.
    from deps.db import SessionLocal

    try:
        with SessionLocal() as db, db.begin():
            wipe(db)
            insert_all(db)
    except OperationalError as error:
        print(f"could not connect to the database: {error}", file=sys.stderr)
        print("is `bun run docker:dev` running?", file=sys.stderr)
        return 1

    print(f"seeded {SEED_EMAIL} / {SEED_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

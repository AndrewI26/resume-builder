"""Test fixtures.

The models are portable across both databases the app runs on, so this suite
is too. It defaults to a throwaway SQLite file, which needs nothing running and
is what the desktop app uses. Point ``TEST_DATABASE_URL`` at a Postgres to run
the identical tests against the hosted app's database — CI does both, and that
pairing is what keeps the two dialects honest. A ``<POSTGRES_DB>_test``
database is created on first run if it is missing.

Every test runs inside a transaction that is rolled back afterwards, so the
endpoints' own ``commit()`` calls are contained and tests stay independent.
"""

import os
import tempfile
from collections.abc import Generator, Iterator, Sequence
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

# A file rather than ``:memory:``: the suite hands the engine to a TestClient
# that serves sync endpoints from a threadpool, and an in-memory database is
# private to the connection that opened it.
_SQLITE_FILE = Path(tempfile.gettempdir()) / "resume-builder-tests.sqlite"


def _test_database_url() -> str:
    configured = os.getenv("TEST_DATABASE_URL")
    if configured:
        return configured

    return f"sqlite+pysqlite:///{_SQLITE_FILE}"


def postgres_url() -> str:
    """The dev Postgres' test database, for tests that need a real Postgres."""
    user = os.getenv("POSTGRES_USER", "resume_user")
    password = os.getenv("POSTGRES_PASSWORD", "resume_pass")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "resume_db")
    host = os.getenv("POSTGRES_HOST", "localhost")

    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}_test"


# Must be set before importing anything that reads settings: deps.db builds its
# engine at import time, and security caches the signing key.
TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from db import Base, prepare_sqlite
from deps.db import get_db
from enums import DEFAULT_SECTION_ORDER, ResumeSectionType
from main import app
from models.bullet_points import BulletPoint
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.resume_section import ResumeSection
from models.skill import Skill
from models.user import User
from services.security import (
    ACCESS_TOKEN_COOKIE_NAME,
    create_access_token,
    hash_password,
)


def _create_database_if_missing(url: str) -> None:
    if not url.startswith("postgresql"):
        # SQLite creates its file on first connect, and there is no server to
        # ask for a database list
        return

    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    admin_url = urlunsplit(parts._replace(path="/postgres"))

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    _create_database_if_missing(TEST_DATABASE_URL)

    engine = prepare_sqlite(create_engine(TEST_DATABASE_URL))
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        _SQLITE_FILE.unlink(missing_ok=True)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose work is discarded once the test finishes.

    ``join_transaction_mode="create_savepoint"`` means a ``commit()`` inside an
    endpoint releases a savepoint instead of ending the outer transaction, so
    the rollback below still undoes everything.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


class MakeUser(Protocol):
    def __call__(self, email: str = ..., password: str | None = ...) -> User: ...


@pytest.fixture
def make_user(db: Session) -> MakeUser:
    """Insert a user directly.

    ``password`` is only hashed when a test actually needs to log in, since
    bcrypt is deliberately slow.
    """

    def _make_user(
        email: str = "user@example.com", password: str | None = None
    ) -> User:
        hashed_password = (
            hash_password(password) if password is not None else "not-a-real-hash"
        )
        user = User(email=email, hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make_user


@pytest.fixture
def user(make_user: MakeUser) -> User:
    return make_user()


@pytest.fixture
def other_user(make_user: MakeUser) -> User:
    return make_user("other@example.com")


@pytest.fixture
def make_expirence(db: Session):
    """Insert an experience directly, bypassing the endpoints under test."""

    def _make_expirence(
        user: User,
        *,
        company: str = "Acme",
        position: str = "Engineer",
        duration: str = "2020 - 2022",
        location: str = "New York, NY",
        bullets: Sequence[str] = ("First bullet", "Second bullet"),
    ) -> Expirence:
        bullet_rows = [BulletPoint(text=text, bolded=[]) for text in bullets]
        db.add_all(bullet_rows)
        db.flush()

        expirence = Expirence(
            user_id=user.id,
            company=company,
            position=position,
            duration=duration,
            location=location,
            bullet_points=[bullet.id for bullet in bullet_rows],
        )
        db.add(expirence)
        db.commit()
        db.refresh(expirence)
        return expirence

    return _make_expirence


@pytest.fixture
def make_education(db: Session):
    """Insert an education directly, bypassing the endpoints under test."""

    def _make_education(
        user: User,
        *,
        name: str = "State University",
        subheading: str = "BSc Computer Science",
        duration: str = "2016 - 2020",
        location: str = "Boston, MA",
    ) -> Education:
        education = Education(
            user_id=user.id,
            name=name,
            subheading=subheading,
            duration=duration,
            location=location,
        )
        db.add(education)
        db.commit()
        db.refresh(education)
        return education

    return _make_education


@pytest.fixture
def make_project(db: Session):
    """Insert a project directly, bypassing the endpoints under test."""

    def _make_project(
        user: User,
        *,
        name: str = "Resume Builder",
        link: str | None = "https://example.com/project",
        technologies: Sequence[str] = ("Python", "FastAPI"),
        bullets: Sequence[str] = ("First bullet", "Second bullet"),
    ) -> Project:
        bullet_rows = [BulletPoint(text=text, bolded=[]) for text in bullets]
        db.add_all(bullet_rows)
        db.flush()

        project = Project(
            user_id=user.id,
            name=name,
            link=link,
            technologies=list(technologies),
            bullet_points=[bullet.id for bullet in bullet_rows],
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    return _make_project


@pytest.fixture
def make_personal_info(db: Session):
    """Insert a user's personal info directly, bypassing the endpoints."""

    _UNSET: Any = object()

    def _make_personal_info(
        user: User,
        *,
        email: str | None = "me@example.com",
        phone_number: str | None = "+1 555 0100",
        address: str | None = "Boston, MA",
        github: dict[str, Any] | None = _UNSET,
        linkedin: dict[str, Any] | None = _UNSET,
        portfolio: dict[str, Any] | None = _UNSET,
    ) -> PersonalInfo:
        if github is _UNSET:
            github = {"url": "https://github.com/example", "label": "GitHub"}
        if linkedin is _UNSET:
            linkedin = {"url": "https://linkedin.com/in/example", "label": "LinkedIn"}
        if portfolio is _UNSET:
            portfolio = {"url": "https://example.com", "label": "Portfolio"}

        personal_info = PersonalInfo(
            user_id=user.id,
            email=email,
            phone_number=phone_number,
            address=address,
            github=github,
            linkedin=linkedin,
            portfolio=portfolio,
        )
        db.add(personal_info)
        db.commit()
        db.refresh(personal_info)
        return personal_info

    return _make_personal_info


@pytest.fixture
def make_skill(db: Session):
    """Insert a skill list directly, bypassing the endpoints under test."""

    def _make_skill(
        user: User,
        *,
        name: str = "Languages",
        items: Sequence[str] = ("Python", "Go", "SQL"),
        position: int = 0,
    ) -> Skill:
        skill = Skill(
            user_id=user.id,
            name=name,
            items=list(items),
            position=position,
        )
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill

    return _make_skill


@pytest.fixture
def auth(client: TestClient):
    """Sign the client in as a given user for subsequent requests.

    The cookie is injected without a domain, which httpx sends on every
    request but which the server's ``delete_cookie`` header cannot match. Tests
    that care about the cookie being *cleared* should log in through
    ``/auth/login`` instead.
    """

    def _auth(user: User) -> TestClient:
        client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, create_access_token(user.id))
        return client

    return _auth


@pytest.fixture
def make_resume(db: Session):
    """Insert a resume directly, bypassing the endpoints under test."""

    def _make_resume(
        user: User,
        *,
        title: str = "Software Engineer",
        template: str = "jakes",
        full_name: str | None = "Ada Lovelace",
        personal_info: PersonalInfo | None = None,
        section_order: Sequence[ResumeSectionType] | None = None,
    ) -> Resume:
        order = DEFAULT_SECTION_ORDER if section_order is None else section_order
        resume = Resume(
            user_id=user.id,
            title=title,
            template=template,
            full_name=full_name,
            personal_info_id=None if personal_info is None else personal_info.id,
            section_order=[section_type.value for section_type in order],
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        return resume

    return _make_resume


@pytest.fixture
def attach_section(db: Session):
    """Add one section to a resume at a given position within its type."""

    def _attach_section(
        resume: Resume,
        section_type: ResumeSectionType,
        section_id,
        position: int = 0,
    ) -> ResumeSection:
        row = ResumeSection(
            resume_id=resume.id,
            section_type=section_type,
            section_id=section_id,
            position=position,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _attach_section


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Run ``async def`` tests on asyncio only, not the trio leg as well."""
    return "asyncio"

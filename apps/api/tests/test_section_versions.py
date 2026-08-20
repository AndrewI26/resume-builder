"""Version history written by the section endpoints.

`record_version` itself is covered in `test_record_section.py`; what matters
here is that every create endpoint calls it, and calls it with the section type
and snapshot that belong to the row it just wrote.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.section_version import SectionVersion
from models.user import User

EDUCATION = {
    "name": "State University",
    "subheading": "BSc Computer Science",
    "duration": "2016 - 2020",
    "location": "Boston, MA",
}
EXPERIENCE = {
    "company": "Acme",
    "position": "Engineer",
    "duration": "2020 - 2022",
    "location": "New York, NY",
    "bullet_points": [{"text": "Shipped it", "bolded": [[0, 6]]}],
}
PERSONAL_INFO = {"email": "me@example.com", "phone_number": "+1 555 0100"}
PROJECT = {
    "name": "Resume Builder",
    "link": "https://example.com/project",
    "technologies": ["Python", "FastAPI"],
    "bullet_points": [{"text": "Wrote it", "bolded": []}],
}
SKILL = {"name": "Languages", "items": ["Python", "Go"]}

# the fourth element is a payload the endpoint must reject: an empty body is
# missing required fields everywhere except personal info, where every field is
# optional and only an overlong one fails validation
SECTIONS = [
    ("/education/", EDUCATION, SectionType.EDUCATION, {}),
    ("/experience/", EXPERIENCE, SectionType.EXPERIENCE, {}),
    ("/personal-info/", PERSONAL_INFO, SectionType.PERSONAL_INFO, {"email": "e" * 300}),
    ("/project/", PROJECT, SectionType.PROJECT, {}),
    ("/skill/", SKILL, SectionType.SKILL, {}),
]
SECTION_IDS = [path.strip("/") for path, *_ in SECTIONS]


def versions(db: Session) -> list[SectionVersion]:
    db.expire_all()
    return list(db.scalars(select(SectionVersion).order_by(SectionVersion.version)))


def version_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SectionVersion)) or 0


@pytest.mark.parametrize(
    ("path", "body", "section_type", "invalid"), SECTIONS, ids=SECTION_IDS
)
class TestCreateRecordsAVersion:
    def test_writes_exactly_one_version(
        self, auth, user: User, db: Session, path, body, section_type, invalid
    ):
        auth(user).post(path, json=body)

        assert version_count(db) == 1

    def test_the_first_version_is_a_create(
        self, auth, user: User, db: Session, path, body, section_type, invalid
    ):
        auth(user).post(path, json=body)

        row = versions(db)[0]
        assert row.version == 1
        assert row.operation == OperationType.CREATE

    def test_records_the_section_type(
        self, auth, user: User, db: Session, path, body, section_type, invalid
    ):
        auth(user).post(path, json=body)

        assert versions(db)[0].section_type == section_type

    def test_points_at_the_row_that_was_created(
        self, auth, user: User, db: Session, path, body, section_type, invalid
    ):
        response = auth(user).post(path, json=body)

        assert str(versions(db)[0].section_id) == response.json()["id"]

    def test_snapshots_what_the_endpoint_returned(
        self, auth, user: User, db: Session, path, body, section_type, invalid
    ):
        response = auth(user).post(path, json=body)

        assert versions(db)[0].snapshot == response.json()

    def test_belongs_to_the_caller(
        self, auth, user: User, db: Session, path, body, section_type, invalid
    ):
        auth(user).post(path, json=body)

        assert versions(db)[0].user_id == user.id

    def test_a_rejected_create_records_nothing(
        self, auth, user: User, db: Session, path, body, section_type, invalid
    ):
        response = auth(user).post(path, json=invalid)

        assert response.status_code == 422
        assert version_count(db) == 0

    def test_an_unauthenticated_create_records_nothing(
        self, client: TestClient, db: Session, path, body, section_type, invalid
    ):
        response = client.post(path, json=body)

        assert response.status_code == 401
        assert version_count(db) == 0


class TestAcrossSections:
    def test_each_created_section_starts_its_own_history(
        self, auth, user: User, db: Session
    ):
        for path, body, *_ in SECTIONS:
            auth(user).post(path, json=body)

        rows = versions(db)
        assert len(rows) == len(SECTIONS)
        assert {row.version for row in rows} == {1}
        assert len({row.section_id for row in rows}) == len(SECTIONS)

    def test_records_the_type_of_every_section(self, auth, user: User, db: Session):
        for path, body, *_ in SECTIONS:
            auth(user).post(path, json=body)

        assert {row.section_type for row in versions(db)} == {
            section_type for _, _, section_type, _ in SECTIONS
        }

    def test_two_rows_of_the_same_type_get_separate_histories(
        self, auth, user: User, db: Session
    ):
        auth(user).post("/skill/", json=SKILL)
        auth(user).post("/skill/", json={**SKILL, "name": "Tools"})

        rows = versions(db)
        assert [row.version for row in rows] == [1, 1]
        assert len({row.section_id for row in rows}) == 2

    def test_each_user_owns_their_own_versions(
        self, auth, user: User, other_user: User, db: Session
    ):
        auth(user).post("/skill/", json=SKILL)
        auth(other_user).post("/skill/", json=SKILL)

        assert {row.user_id for row in versions(db)} == {user.id, other_user.id}

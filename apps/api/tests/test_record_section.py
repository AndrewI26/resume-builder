from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.section_version import SectionVersion
from models.user import User
from services.record_section import record_version


def versions(db: Session, section_id) -> list[SectionVersion]:
    db.expire_all()
    stmt = (
        select(SectionVersion)
        .where(SectionVersion.section_id == section_id)
        .order_by(SectionVersion.version)
    )
    return list(db.scalars(stmt))


def version_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SectionVersion)) or 0


def snapshot(**overrides):
    body = {"id": str(uuid4()), "name": "State University"}
    body.update(overrides)
    return body


class TestNumbering:
    def test_the_first_version_of_a_section_is_one(self, db: Session, user: User):
        section_id = uuid4()

        record_version(
            db,
            user.id,
            SectionType.EDUCATION,
            section_id,
            OperationType.CREATE,
            snapshot(),
        )

        assert [row.version for row in versions(db, section_id)] == [1]

    def test_each_call_increments_the_version(self, db: Session, user: User):
        section_id = uuid4()

        for operation in (
            OperationType.CREATE,
            OperationType.UPDATE,
            OperationType.DELETE,
        ):
            record_version(
                db, user.id, SectionType.SKILL, section_id, operation, snapshot()
            )

        assert [row.version for row in versions(db, section_id)] == [1, 2, 3]

    def test_sections_are_numbered_independently(self, db: Session, user: User):
        first, second = uuid4(), uuid4()

        record_version(
            db, user.id, SectionType.SKILL, first, OperationType.CREATE, snapshot()
        )
        record_version(
            db, user.id, SectionType.SKILL, first, OperationType.UPDATE, snapshot()
        )
        record_version(
            db, user.id, SectionType.SKILL, second, OperationType.CREATE, snapshot()
        )

        assert [row.version for row in versions(db, first)] == [1, 2]
        assert [row.version for row in versions(db, second)] == [1]

    def test_keeps_numbering_a_section_after_its_delete(self, db: Session, user: User):
        """A delete is recorded, not terminal: the id can be versioned again."""
        section_id = uuid4()

        record_version(
            db, user.id, SectionType.PROJECT, section_id, OperationType.CREATE, {}
        )
        record_version(
            db, user.id, SectionType.PROJECT, section_id, OperationType.DELETE, {}
        )

        assert [row.operation for row in versions(db, section_id)] == [
            OperationType.CREATE,
            OperationType.DELETE,
        ]


class TestStoredRow:
    def test_stores_every_field_it_was_given(self, db: Session, user: User):
        section_id = uuid4()
        body = snapshot(name="Renamed")

        record_version(
            db,
            user.id,
            SectionType.EDUCATION,
            section_id,
            OperationType.UPDATE,
            body,
        )

        row = versions(db, section_id)[0]
        assert row.user_id == user.id
        assert row.section_type == SectionType.EDUCATION
        assert row.section_id == section_id
        assert row.operation == OperationType.UPDATE
        assert row.snapshot == body

    def test_stores_a_nested_snapshot_verbatim(self, db: Session, user: User):
        section_id = uuid4()
        body = {
            "id": str(section_id),
            "company": "Acme",
            "bullet_points": [{"text": "Shipped it", "bolded": [[0, 6]]}],
        }

        record_version(
            db,
            user.id,
            SectionType.EXPERIENCE,
            section_id,
            OperationType.CREATE,
            body,
        )

        assert versions(db, section_id)[0].snapshot == body

    def test_accepts_an_empty_snapshot(self, db: Session, user: User):
        section_id = uuid4()

        record_version(
            db, user.id, SectionType.PERSONAL_INFO, section_id, OperationType.DELETE, {}
        )

        assert versions(db, section_id)[0].snapshot == {}

    def test_commits_the_row(self, db: Session, user: User):
        """The caller relies on this to land its own pending writes too."""
        section_id = uuid4()

        record_version(
            db, user.id, SectionType.SKILL, section_id, OperationType.CREATE, snapshot()
        )
        db.rollback()

        assert version_count(db) == 1

    def test_records_the_same_section_id_for_two_users(
        self, db: Session, user: User, other_user: User
    ):
        """`section_id` alone does not identify a row; the user scopes reads."""
        section_id = uuid4()

        record_version(
            db, user.id, SectionType.SKILL, section_id, OperationType.CREATE, snapshot()
        )
        record_version(
            db,
            other_user.id,
            SectionType.SKILL,
            section_id,
            OperationType.UPDATE,
            snapshot(),
        )

        assert [row.user_id for row in versions(db, section_id)] == [
            user.id,
            other_user.id,
        ]

"""The history, read as the thing a sync will replay.

Every mutation already wrote an entry here; what these tests pin down is the
two properties a sync depends on and nothing else needed before.

A record's ``version`` is what decides whether two sides disagree, so it has to
count that record's own history and no one else's. A user's ``seq`` is what
decides the order changes are replayed in, so it has to be a single sequence
covering every kind of record — sections and resumes together — with no gaps
that would make "everything since 812" ambiguous.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enums import OperationType, SectionType
from models.section_version import SectionVersion
from models.user import User
from services.record_section import record_version


def entries(db: Session, user: User) -> list[SectionVersion]:
    return list(
        db.scalars(
            select(SectionVersion)
            .where(SectionVersion.user_id == user.id)
            .order_by(SectionVersion.seq)
        ).all()
    )


class TestTheSequence:
    def test_it_counts_up_across_different_records(
        self, db: Session, user: User
    ) -> None:
        for _ in range(3):
            record_version(
                db,
                user.id,
                SectionType.SKILL,
                uuid.uuid4(),
                OperationType.CREATE,
                {},
            )

        assert [entry.seq for entry in entries(db, user)] == [1, 2, 3]

    def test_it_counts_up_across_different_kinds_of_record(
        self, db: Session, user: User
    ) -> None:
        """One sequence, or a sync would have to merge several."""
        for section_type in (
            SectionType.SKILL,
            SectionType.RESUME,
            SectionType.EDUCATION,
        ):
            record_version(
                db, user.id, section_type, uuid.uuid4(), OperationType.CREATE, {}
            )

        assert [entry.seq for entry in entries(db, user)] == [1, 2, 3]

    def test_each_user_has_their_own(
        self, db: Session, user: User, other_user: User
    ) -> None:
        """Otherwise one person's edits would advance another's cursor."""
        record_version(
            db, user.id, SectionType.SKILL, uuid.uuid4(), OperationType.CREATE, {}
        )
        record_version(
            db, other_user.id, SectionType.SKILL, uuid.uuid4(), OperationType.CREATE, {}
        )

        assert [entry.seq for entry in entries(db, user)] == [1]
        assert [entry.seq for entry in entries(db, other_user)] == [1]

    def test_it_is_refused_twice(self, db: Session, user: User) -> None:
        """The constraint is what makes the ordering true, not the arithmetic.

        Reading the highest number and adding one is not atomic, so a duplicate
        has to be impossible at the database rather than merely unlikely above
        it.
        """
        record_version(
            db, user.id, SectionType.SKILL, uuid.uuid4(), OperationType.CREATE, {}
        )

        db.add(
            SectionVersion(
                user_id=user.id,
                section_type=SectionType.SKILL,
                section_id=uuid.uuid4(),
                version=1,
                seq=1,
                operation=OperationType.CREATE,
                snapshot={},
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestTheVersion:
    def test_it_counts_one_record_rather_than_all_of_them(
        self, db: Session, user: User
    ) -> None:
        first, second = uuid.uuid4(), uuid.uuid4()

        record_version(db, user.id, SectionType.SKILL, first, OperationType.CREATE, {})
        record_version(db, user.id, SectionType.SKILL, first, OperationType.UPDATE, {})
        record_version(db, user.id, SectionType.SKILL, second, OperationType.CREATE, {})

        versions = {(e.section_id, e.version) for e in entries(db, user)}
        assert versions == {(first, 1), (first, 2), (second, 1)}


class TestResumesAreRecorded:
    """A resume is edited like anything else and has to travel like anything else."""

    def test_creating_one_is_recorded(self, auth, db: Session, user: User) -> None:
        client = auth(user)
        response = client.post("/resumes/", json={"title": "Backend roles"})
        assert response.status_code == 201

        recorded = entries(db, user)
        assert [(e.section_type, e.operation) for e in recorded] == [
            (SectionType.RESUME, OperationType.CREATE)
        ]
        assert recorded[0].snapshot["title"] == "Backend roles"

    def test_editing_one_is_recorded(self, auth, db: Session, user: User) -> None:
        client = auth(user)
        created = client.post("/resumes/", json={"title": "Backend roles"}).json()

        client.put(
            f"/resumes/{created['id']}",
            json={"title": "Frontend roles", "section_order": []},
        )

        recorded = entries(db, user)
        assert [e.operation for e in recorded] == [
            OperationType.CREATE,
            OperationType.UPDATE,
        ]
        assert recorded[-1].snapshot["title"] == "Frontend roles"
        assert recorded[-1].version == 2

    def test_deleting_one_keeps_what_it_was(
        self, auth, db: Session, user: User
    ) -> None:
        """The history is the only place a deleted resume still exists."""
        client = auth(user)
        created = client.post("/resumes/", json={"title": "Backend roles"}).json()

        client.delete(f"/resumes/{created['id']}")

        recorded = entries(db, user)
        assert recorded[-1].operation == OperationType.DELETE
        assert recorded[-1].snapshot["title"] == "Backend roles"

    def test_changing_the_membership_is_a_new_version_of_the_resume(
        self, auth, db: Session, user: User, make_education
    ) -> None:
        """The sections a resume picks are part of it, not a record of their own."""
        client = auth(user)
        education = make_education(user)
        created = client.post("/resumes/", json={"title": "Backend roles"}).json()

        response = client.put(
            f"/resumes/{created['id']}/sections",
            json={
                "sections": [
                    {"section_type": "education", "section_id": str(education.id)}
                ]
            },
        )
        assert response.status_code == 200

        recorded = entries(db, user)
        assert recorded[-1].section_type == SectionType.RESUME
        assert recorded[-1].operation == OperationType.UPDATE
        assert recorded[-1].snapshot["sections"] == [
            {
                "section_type": "education",
                "section_id": str(education.id),
                "position": 0,
            }
        ]


class TestEveryChangeIsRecorded:
    """Not only creations.

    The history was written on create and nowhere else, so a section edited or
    deleted left no trace — the two operations the enum names but nothing ever
    wrote. Nothing read the history, so nothing noticed. Sync reads it, and a
    library edited offline would have had nothing to send.
    """

    def test_editing_a_section(self, auth, db: Session, user: User, make_education):
        education = make_education(user, name="State University")

        response = auth(user).put(
            f"/education/{education.id}",
            json={
                "name": "Renamed",
                "subheading": "BSc",
                "duration": "2016 - 2020",
                "location": "Boston, MA",
            },
        )
        assert response.status_code == 200

        recorded = entries(db, user)
        assert [e.operation for e in recorded] == [OperationType.UPDATE]
        assert recorded[-1].snapshot["name"] == "Renamed"

    def test_deleting_a_section_keeps_what_it_was(
        self, auth, db: Session, user: User, make_education
    ):
        """The history is the only place a deleted section still exists."""
        education = make_education(user, name="State University")

        assert auth(user).delete(f"/education/{education.id}").status_code == 200

        recorded = entries(db, user)
        assert recorded[-1].operation == OperationType.DELETE
        assert recorded[-1].snapshot["name"] == "State University"

    def test_a_records_versions_count_up_through_its_life(
        self, auth, db: Session, user: User
    ):
        client = auth(user)
        created = client.post(
            "/education/",
            json={
                "name": "First",
                "subheading": "BSc",
                "duration": "2016 - 2020",
                "location": "Boston, MA",
            },
        ).json()

        client.put(
            f"/education/{created['id']}",
            json={
                "name": "Second",
                "subheading": "BSc",
                "duration": "2016 - 2020",
                "location": "Boston, MA",
            },
        )
        client.delete(f"/education/{created['id']}")

        recorded = entries(db, user)
        assert [(e.version, e.operation) for e in recorded] == [
            (1, OperationType.CREATE),
            (2, OperationType.UPDATE),
            (3, OperationType.DELETE),
        ]

    @pytest.mark.parametrize(
        ("path", "payload", "record_type"),
        [
            (
                "/skill/",
                {"name": "Languages", "items": ["Python"], "position": 0},
                SectionType.SKILL,
            ),
            (
                "/personal-info/",
                {"email": "ada@example.com"},
                SectionType.PERSONAL_INFO,
            ),
            (
                "/project/",
                {"name": "A project", "technologies": [], "bullet_points": []},
                SectionType.PROJECT,
            ),
            (
                "/experience/",
                {
                    "company": "Acme",
                    "position": "Engineer",
                    "duration": "2020 - 2022",
                    "location": "New York, NY",
                    "bullet_points": [],
                },
                SectionType.EXPERIENCE,
            ),
        ],
    )
    def test_every_kind_of_section_records_all_three(
        self, auth, db: Session, user: User, path, payload, record_type
    ):
        """One router doing it and another not is exactly how sync loses work."""
        client = auth(user)
        created = client.post(path, json=payload).json()

        client.put(f"{path}{created['id']}", json=payload)
        client.delete(f"{path}{created['id']}")

        recorded = [e for e in entries(db, user) if e.section_type == record_type]
        assert [e.operation for e in recorded] == [
            OperationType.CREATE,
            OperationType.UPDATE,
            OperationType.DELETE,
        ]

"""Importing and exporting a library's sections as one JSON document."""

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enums import OperationType
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.section_version import SectionVersion
from models.skill import Skill
from models.user import User
from schemas.portable import format_bold, parse_bold
from services.bullet_points import bullet_points_by_id, hydrate

LIBRARY: dict[str, Any] = {
    "personal_info": [
        {
            "email": "ada@example.com",
            "phone_number": "+1 555 0100",
            "github": {"url": "https://github.com/ada", "label": "ada"},
        }
    ],
    "education": [
        {
            "name": "McMaster University",
            "subheading": "B.Eng. Software",
            "duration": "2019 - 2024",
            "location": "Hamilton, ON",
            "coursework": ["Data Structures", "Algorithms"],
        }
    ],
    "experience": [
        {
            "company": "Acme",
            "position": "Engineer",
            "duration": "2024 - Present",
            "location": "Toronto, ON",
            "bullet_points": [
                "Shipped the thing",
                "Cut costs by **40%** in **one** quarter",
            ],
        },
        {
            "company": "Initech",
            "position": "Intern",
            "duration": "2023",
            "location": "Remote",
        },
    ],
    "projects": [
        {
            "name": "Whiz",
            "github": "https://github.com/ada/whiz",
            "technologies": ["Go"],
            "bullet_points": ["A web framework"],
        }
    ],
    "skills": [{"name": "Languages", "items": ["Python", "Go"]}],
}

SECTION_MODELS = (PersonalInfo, Education, Expirence, Project, Skill)


@pytest.fixture(autouse=True)
def no_autoflush(db: Session) -> None:
    """Run these the way the app's sessions do (see ``deps.db``).

    An import writes many records and their history entries in one
    transaction, so whether pending rows are visible to its own queries is
    exactly the thing that differs between the test session and the real one.
    """
    db.autoflush = False


def library(**changes: Any) -> dict[str, Any]:
    body = copy.deepcopy(LIBRARY)
    body.update(changes)
    return body


def count(db: Session, model: Any, user: User) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(model).where(model.user_id == user.id)
        )
        or 0
    )


def total_sections(db: Session, user: User) -> int:
    return sum(count(db, model, user) for model in SECTION_MODELS)


class TestImport:
    def test_adds_every_section(self, auth, user: User, db: Session) -> None:
        response = auth(user).post("/library/import", json=LIBRARY)

        assert response.status_code == 200
        assert response.json() == {
            "dry_run": False,
            "personal_info": 1,
            "education": 1,
            "experience": 2,
            "projects": 1,
            "skills": 1,
        }
        assert count(db, Expirence, user) == 2
        assert count(db, Project, user) == 1

    def test_makes_no_resume(self, auth, user: User, db: Session) -> None:
        auth(user).post("/library/import", json=LIBRARY)

        assert count(db, Resume, user) == 0

    def test_turns_markers_into_bold(self, auth, user: User, db: Session) -> None:
        auth(user).post("/library/import", json=LIBRARY)

        acme = db.scalars(
            select(Expirence).where(
                Expirence.user_id == user.id, Expirence.company == "Acme"
            )
        ).one()
        bullets = hydrate(
            acme.bullet_points, bullet_points_by_id(db, acme.bullet_points)
        )
        assert [(bullet.text, bullet.bolded) for bullet in bullets] == [
            ("Shipped the thing", []),
            ("Cut costs by 40% in one quarter", [(13, 15), (20, 22)]),
        ]

    def test_the_sections_show_up_through_their_endpoints(
        self, auth, user: User
    ) -> None:
        client = auth(user)
        client.post("/library/import", json=LIBRARY)

        projects = client.get("/project/").json()
        assert [p["github"] for p in projects] == ["https://github.com/ada/whiz"]
        info = client.get("/personal-info/").json()
        assert info[0]["github"] == {"url": "https://github.com/ada", "label": "ada"}

    def test_records_a_history_entry_for_every_section(
        self, auth, user: User, db: Session
    ) -> None:
        auth(user).post("/library/import", json=LIBRARY)

        entries = list(
            db.scalars(
                select(SectionVersion)
                .where(SectionVersion.user_id == user.id)
                .order_by(SectionVersion.seq)
            )
        )
        assert len(entries) == total_sections(db, user)
        assert {entry.operation for entry in entries} == {OperationType.CREATE}
        assert [entry.seq for entry in entries] == list(range(1, len(entries) + 1))

    def test_adds_to_what_is_already_there(
        self, auth, user: User, db: Session, make_expirence, make_skill
    ) -> None:
        make_expirence(user)
        make_skill(user, name="Tools", position=4)

        auth(user).post("/library/import", json=LIBRARY)

        assert count(db, Expirence, user) == 3
        imported = db.scalars(
            select(Skill).where(Skill.user_id == user.id, Skill.name == "Languages")
        ).one()
        assert imported.position == 5

    def test_every_list_is_optional(self, auth, user: User, db: Session) -> None:
        response = auth(user).post(
            "/library/import", json={"experience": LIBRARY["experience"]}
        )

        assert response.status_code == 200
        assert count(db, Expirence, user) == 2

    def test_an_empty_file_adds_nothing(self, auth, user: User, db: Session) -> None:
        response = auth(user).post("/library/import", json={})

        assert response.status_code == 200
        assert total_sections(db, user) == 0


class TestDryRun:
    def test_reports_without_writing(self, auth, user: User, db: Session) -> None:
        response = auth(user).post("/library/import?dry_run=true", json=LIBRARY)

        assert response.status_code == 200
        assert response.json()["dry_run"] is True
        assert response.json()["experience"] == 2
        assert total_sections(db, user) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(SectionVersion)
                .where(SectionVersion.user_id == user.id)
            )
            == 0
        )


class TestRejection:
    @pytest.mark.parametrize(
        ("body", "location"),
        [
            (
                library(education=[dict(LIBRARY["education"][0], degree="BEng")]),
                ["body", "education", 0, "degree"],
            ),
            (
                library(projects=[dict(LIBRARY["projects"][0], name="a" * 256)]),
                ["body", "projects", 0, "name"],
            ),
            (
                library(skills=[{"items": ["Go"]}]),
                ["body", "skills", 0, "name"],
            ),
            (
                library(experience=[dict(LIBRARY["experience"][0], key="acme")]),
                ["body", "experience", 0, "key"],
            ),
            (library(resumes=[]), ["body", "resumes"]),
            (library(version=1), ["body", "version"]),
        ],
        ids=[
            "unknown-field",
            "field-too-long",
            "missing-field",
            "keys-are-not-part-of-it",
            "resumes-are-not-part-of-it",
            "no-version-field",
        ],
    )
    def test_refuses_and_writes_nothing(
        self, auth, user: User, db: Session, body, location
    ) -> None:
        response = auth(user).post("/library/import", json=body)

        assert response.status_code == 422
        assert location in [error["loc"] for error in response.json()["detail"]]
        assert total_sections(db, user) == 0

    def test_reports_every_problem_at_once(self, auth, user: User) -> None:
        body = library(
            education=[dict(LIBRARY["education"][0], degree="BEng")],
            skills=[{"items": ["Go"]}],
        )

        detail = auth(user).post("/library/import", json=body).json()["detail"]

        assert len(detail) == 2

    @pytest.mark.parametrize(
        "bullet", ["Cut costs by **40%", "**Cut** costs **by 40%", "Cut **** costs"]
    )
    def test_refuses_markers_that_do_not_pair_up(
        self, auth, user: User, db: Session, bullet: str
    ) -> None:
        body = library(
            experience=[dict(LIBRARY["experience"][0], bullet_points=["Fine", bullet])]
        )

        response = auth(user).post("/library/import", json=body)

        assert response.status_code == 422
        [error] = response.json()["detail"]
        assert error["loc"] == ["body", "experience", 0, "bullet_points", 1]
        assert bullet in error["msg"]
        assert total_sections(db, user) == 0

    def test_needs_a_signed_in_user(self, client: TestClient) -> None:
        assert client.post("/library/import", json=LIBRARY).status_code == 401


class TestExport:
    def test_round_trips_into_another_account(
        self, auth, user: User, other_user: User, db: Session
    ) -> None:
        auth(user).post("/library/import", json=LIBRARY)
        exported = auth(user).get("/library/export").json()

        auth(other_user).post("/library/import", json=exported)

        assert auth(other_user).get("/library/export").json() == exported
        assert total_sections(db, other_user) == total_sections(db, user)

    def test_writes_only_the_sections(self, auth, user: User, make_resume) -> None:
        make_resume(user)

        exported = auth(user).get("/library/export").json()

        assert set(exported) == {
            "personal_info",
            "education",
            "experience",
            "projects",
            "skills",
        }

    def test_is_a_download(self, auth, user: User) -> None:
        response = auth(user).get("/library/export")

        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]

    def test_only_contains_the_callers_sections(
        self, auth, user: User, other_user: User
    ) -> None:
        auth(other_user).post("/library/import", json=LIBRARY)

        exported = auth(user).get("/library/export").json()

        assert exported["experience"] == []

    def test_marks_bold_with_asterisks(self, auth, user: User) -> None:
        auth(user).post("/library/import", json=LIBRARY)

        exported = auth(user).get("/library/export").json()

        acme = next(e for e in exported["experience"] if e["company"] == "Acme")
        assert acme["bullet_points"] == LIBRARY["experience"][0]["bullet_points"]


class TestBoldMarkers:
    @pytest.mark.parametrize(
        ("marked", "text", "bolded"),
        [
            ("No bold here", "No bold here", []),
            ("**Led** a team", "Led a team", [(0, 2)]),
            ("Cut costs by **40%** fast", "Cut costs by 40% fast", [(13, 15)]),
            ("Cut costs by **40%**", "Cut costs by 40%", [(13, 15)]),
            ("**All of it**", "All of it", [(0, 8)]),
            ("**a** and **b** and **c**", "a and b and c", [(0, 0), (6, 6), (12, 12)]),
            ("Single * star stays", "Single * star stays", []),
        ],
        ids=["none", "start", "middle", "end", "whole", "several", "single-star"],
    )
    def test_parses_and_formats_back(
        self, marked: str, text: str, bolded: list[tuple[int, int]]
    ) -> None:
        assert parse_bold(marked) == (text, bolded)
        assert format_bold(text, bolded) == marked

    @pytest.mark.parametrize(
        "marked", ["**open", "close**", "**a** **b", "empty ****", "***"]
    )
    def test_refuses_unbalanced_or_empty_markers(self, marked: str) -> None:
        with pytest.raises(ValueError, match="\\*\\*"):
            parse_bold(marked)


class TestSchema:
    def test_describes_the_format(self, client: TestClient) -> None:
        schema = client.get("/library/schema").json()

        assert schema["title"] == "PortableLibrary"
        assert set(schema["properties"]) == {
            "personal_info",
            "education",
            "experience",
            "projects",
            "skills",
        }

    def test_explains_bold_markers(self, client: TestClient) -> None:
        schema = client.get("/library/schema").json()

        bullets = schema["$defs"]["PortableExperience"]["properties"]["bullet_points"]
        assert "**" in bullets["items"]["description"]

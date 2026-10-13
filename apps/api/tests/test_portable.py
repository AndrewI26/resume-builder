"""Importing and exporting a library as one JSON document."""

import copy
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enums import OperationType, ResumeSectionType, SectionType
from models.education import Education
from models.expirence import Expirence
from models.personal_info import PersonalInfo
from models.project import Project
from models.resume import Resume
from models.resume_section import ResumeSection
from models.section_version import SectionVersion
from models.skill import Skill
from models.user import User

LIBRARY: dict[str, Any] = {
    "format": "resume-builder",
    "version": 1,
    "personal_info": [
        {
            "key": "main",
            "email": "ada@example.com",
            "phone_number": "+1 555 0100",
            "github": {"url": "https://github.com/ada", "label": "ada"},
        }
    ],
    "education": [
        {
            "key": "mcmaster",
            "name": "McMaster University",
            "subheading": "B.Eng. Software",
            "duration": "2019 - 2024",
            "location": "Hamilton, ON",
        }
    ],
    "experience": [
        {
            "key": "acme",
            "company": "Acme",
            "position": "Engineer",
            "duration": "2024 - Present",
            "location": "Toronto, ON",
            "bullet_points": ["Shipped the thing", "Cut costs by 40%"],
        },
        {
            "company": "Not on any resume",
            "position": "Intern",
            "duration": "2023",
            "location": "Remote",
        },
    ],
    "projects": [
        {
            "key": "whiz",
            "name": "Whiz",
            "github": "https://github.com/ada/whiz",
            "technologies": ["Go"],
            "bullet_points": ["A web framework"],
        }
    ],
    "skills": [{"key": "langs", "name": "Languages", "items": ["Python", "Go"]}],
    "resumes": [
        {
            "title": "Backend",
            "full_name": "Ada Lovelace",
            "personal_info": "main",
            "section_order": ["skill", "experience", "project", "education"],
            "sections": {
                "experience": ["acme"],
                "project": ["whiz"],
                "education": ["mcmaster"],
                "skill": ["langs"],
            },
        }
    ],
}


@pytest.fixture(autouse=True)
def no_autoflush(db: Session) -> None:
    """Run these the way the app's sessions do (see ``deps.db``).

    An import writes many records that refer to each other in one
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


def total_records(db: Session, user: User) -> int:
    models = (PersonalInfo, Education, Expirence, Project, Skill, Resume)
    return sum(count(db, model, user) for model in models)


class TestImport:
    def test_creates_every_section_and_resume(
        self, auth, user: User, db: Session
    ) -> None:
        response = auth(user).post("/library/import", json=LIBRARY)

        assert response.status_code == 200
        body = response.json()
        assert body["dry_run"] is False
        assert (
            body["personal_info"],
            body["education"],
            body["experience"],
            body["projects"],
            body["skills"],
        ) == (1, 1, 2, 1, 1)
        assert [resume["title"] for resume in body["resumes"]] == ["Backend"]

        assert count(db, Expirence, user) == 2
        assert count(db, Resume, user) == 1

    def test_the_resume_contains_the_sections_it_named(
        self, auth, user: User, db: Session
    ) -> None:
        body = auth(user).post("/library/import", json=LIBRARY).json()
        resume = db.get(Resume, UUID(body["resumes"][0]["id"]))
        assert resume is not None

        acme = db.scalars(
            select(Expirence).where(
                Expirence.user_id == user.id, Expirence.company == "Acme"
            )
        ).one()
        info = db.scalars(
            select(PersonalInfo).where(PersonalInfo.user_id == user.id)
        ).one()

        refs = {
            (row.section_type, row.section_id)
            for row in db.scalars(
                select(ResumeSection).where(ResumeSection.resume_id == resume.id)
            )
        }
        assert (ResumeSectionType.EXPERIENCE, acme.id) in refs
        assert len(refs) == 4
        assert resume.personal_info_id == info.id
        assert resume.full_name == "Ada Lovelace"

    def test_the_document_renders_the_imported_text(self, auth, user: User) -> None:
        client = auth(user)
        body = client.post("/library/import", json=LIBRARY).json()

        document = client.get(f"/resumes/{body['resumes'][0]['id']}/document").json()

        experience = next(
            block for block in document["sections"] if block["type"] == "experience"
        )
        assert [b["text"] for b in experience["items"][0]["bullet_points"]] == [
            "Shipped the thing",
            "Cut costs by 40%",
        ]
        assert all(b["bolded"] == [] for b in experience["items"][0]["bullet_points"])

    def test_records_a_history_entry_for_every_record(
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
        assert len(entries) == total_records(db, user)
        assert {entry.operation for entry in entries} == {OperationType.CREATE}
        assert [entry.seq for entry in entries] == list(range(1, len(entries) + 1))

        resume_entry = next(e for e in entries if e.section_type is SectionType.RESUME)
        assert len(resume_entry.snapshot["sections"]) == 4

    def test_adds_to_what_is_already_there(
        self, auth, user: User, db: Session, make_expirence, make_skill
    ) -> None:
        make_expirence(user)
        make_skill(user, name="Tools", position=4)

        auth(user).post("/library/import", json=LIBRARY)

        assert count(db, Expirence, user) == 3
        imported = db.scalars(
            select(Skill).where(Skill.user_id == user.id, Skill.name == "Languages")
        ).all()
        assert [skill.position for skill in imported] == [5]

    def test_every_list_is_optional(self, auth, user: User, db: Session) -> None:
        response = auth(user).post(
            "/library/import", json={"experience": LIBRARY["experience"]}
        )

        assert response.status_code == 200
        assert count(db, Expirence, user) == 2

    def test_a_section_type_left_out_of_the_order_is_appended(
        self, auth, user: User, db: Session
    ) -> None:
        resume = dict(LIBRARY["resumes"][0], section_order=["experience"])
        body = auth(user).post("/library/import", json=library(resumes=[resume])).json()

        row = db.get(Resume, UUID(body["resumes"][0]["id"]))
        assert row is not None
        # in the order the file lists them under ``sections``
        assert row.section_order == ["experience", "project", "education", "skill"]


class TestDryRun:
    def test_reports_without_writing(self, auth, user: User, db: Session) -> None:
        response = auth(user).post("/library/import?dry_run=true", json=LIBRARY)

        assert response.status_code == 200
        assert response.json()["dry_run"] is True
        assert response.json()["experience"] == 2
        assert total_records(db, user) == 0
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
        ("body", "expected"),
        [
            (
                library(
                    resumes=[
                        dict(LIBRARY["resumes"][0], sections={"project": ["missing"]})
                    ]
                ),
                "resumes[0].sections.project[0]: no projects entry has key 'missing'",
            ),
            (
                library(resumes=[dict(LIBRARY["resumes"][0], personal_info="nobody")]),
                "resumes[0].personal_info",
            ),
            (
                library(skills=[*LIBRARY["skills"], *LIBRARY["skills"]]),
                "skills[1].key: 'langs' is used twice",
            ),
            (library(version=2), None),
            (library(education=[dict(LIBRARY["education"][0], degree="BEng")]), None),
            (library(projects=[dict(LIBRARY["projects"][0], name="a" * 256)]), None),
            (
                library(
                    resumes=[
                        dict(
                            LIBRARY["resumes"][0],
                            section_order=["skill", "skill"],
                        )
                    ]
                ),
                None,
            ),
        ],
        ids=[
            "unknown-section-key",
            "unknown-personal-info-key",
            "duplicate-key",
            "unsupported-version",
            "unknown-field",
            "field-too-long",
            "repeated-section-type",
        ],
    )
    def test_refuses_and_writes_nothing(
        self, auth, user: User, db: Session, body, expected
    ) -> None:
        response = auth(user).post("/library/import", json=body)

        assert response.status_code == 422
        if expected is not None:
            assert expected in str(response.json()["detail"])
        assert total_records(db, user) == 0

    def test_reports_every_problem_at_once(self, auth, user: User) -> None:
        resume = dict(
            LIBRARY["resumes"][0],
            personal_info="nobody",
            sections={"project": ["a", "b"]},
        )

        detail = str(
            auth(user).post("/library/import", json=library(resumes=[resume])).json()
        )

        assert "personal_info" in detail
        assert "project[0]" in detail
        assert "project[1]" in detail

    def test_needs_a_signed_in_user(self, client: TestClient) -> None:
        assert client.post("/library/import", json=LIBRARY).status_code == 401


class TestExport:
    def test_round_trips_into_another_account(
        self, auth, user: User, other_user: User, db: Session
    ) -> None:
        auth(user).post("/library/import", json=LIBRARY)
        exported = auth(user).get("/library/export").json()

        auth(other_user).post("/library/import", json=exported)
        again = auth(other_user).get("/library/export").json()

        assert strip_keys(again) == strip_keys(exported)
        assert total_records(db, other_user) == total_records(db, user)

    def test_keeps_the_resumes_references(self, auth, user: User) -> None:
        auth(user).post("/library/import", json=LIBRARY)
        exported = auth(user).get("/library/export").json()

        resume = exported["resumes"][0]
        acme = next(e for e in exported["experience"] if e["company"] == "Acme")
        assert resume["sections"]["experience"] == [acme["key"]]
        assert resume["personal_info"] == exported["personal_info"][0]["key"]

    def test_is_a_download(self, auth, user: User) -> None:
        response = auth(user).get("/library/export")

        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]

    def test_only_contains_the_callers_records(
        self, auth, user: User, other_user: User
    ) -> None:
        auth(other_user).post("/library/import", json=LIBRARY)

        exported = auth(user).get("/library/export").json()

        assert exported["experience"] == []
        assert exported["resumes"] == []


class TestSchema:
    def test_describes_the_format(self, client: TestClient) -> None:
        schema = client.get("/library/schema").json()

        assert schema["title"] == "PortableLibrary"
        assert set(schema["properties"]) >= {"experience", "projects", "resumes"}


def strip_keys(exported: dict[str, Any]) -> dict[str, Any]:
    """The library with its ids-as-keys replaced by each entry's position.

    Keys are the records' ids, which differ between accounts by design; what
    has to match is everything else, and which entry each reference points at.
    """
    result = copy.deepcopy(exported)
    positions: dict[str, dict[str, int]] = {}
    for list_name in ("personal_info", "education", "experience", "projects", "skills"):
        positions[list_name] = {}
        for index, item in enumerate(result[list_name]):
            positions[list_name][item.pop("key")] = index

    names = {
        "education": "education",
        "experience": "experience",
        "project": "projects",
        "skill": "skills",
    }
    for resume in result["resumes"]:
        if resume["personal_info"] is not None:
            resume["personal_info"] = positions["personal_info"][
                resume["personal_info"]
            ]
        resume["sections"] = {
            section_type: [positions[names[section_type]][key] for key in keys]
            for section_type, keys in resume["sections"].items()
        }
    return result

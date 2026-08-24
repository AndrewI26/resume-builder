from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enums import ResumeSectionType
from models.resume import Resume
from models.resume_section import ResumeSection

DEFAULT_ORDER = ["skill", "experience", "project", "education"]


def payload(**overrides):
    body = {"title": "Software Engineer"}
    body.update(overrides)
    return body


def replacement(**overrides):
    """A PUT body. Every field is stated, since a replace clears omissions."""
    return payload(**{"full_name": "Ada Lovelace", **overrides})


def resume_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Resume)) or 0


def get_resume(db: Session, resume_id: UUID) -> Resume | None:
    db.expire_all()
    return db.get(Resume, resume_id)


def membership(db: Session, resume_id: UUID) -> list[tuple[str, UUID, int]]:
    db.expire_all()
    stmt = (
        select(ResumeSection)
        .where(ResumeSection.resume_id == resume_id)
        .order_by(ResumeSection.section_type, ResumeSection.position)
    )
    return [
        (row.section_type.value, row.section_id, row.position)
        for row in db.scalars(stmt)
    ]


class TestAuthentication:
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("GET", "/resumes/", None),
            ("POST", "/resumes/", payload()),
            ("GET", f"/resumes/{uuid4()}", None),
            ("PUT", f"/resumes/{uuid4()}", replacement()),
            ("DELETE", f"/resumes/{uuid4()}", None),
            ("GET", f"/resumes/{uuid4()}/sections", None),
            ("PUT", f"/resumes/{uuid4()}/sections", {"sections": []}),
            ("GET", f"/resumes/{uuid4()}/document", None),
        ],
    )
    def test_requires_a_session_cookie(self, client: TestClient, method, path, body):
        response = client.request(method, path, json=body)

        assert response.status_code == 401


class TestCreate:
    def test_creates_a_resume(self, auth, user, db: Session):
        response = auth(user).post("/resumes/", json=payload())

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Software Engineer"
        assert body["template"] == "jakes"
        assert body["section_order"] == DEFAULT_ORDER
        assert resume_count(db) == 1

    def test_defaults_the_section_order_to_jakes_layout(self, auth, user):
        response = auth(user).post("/resumes/", json=payload())

        assert response.json()["section_order"] == DEFAULT_ORDER

    def test_accepts_an_explicit_section_order(self, auth, user):
        order = ["education", "experience"]

        response = auth(user).post("/resumes/", json=payload(section_order=order))

        assert response.status_code == 201
        assert response.json()["section_order"] == order

    def test_rejects_a_repeated_section_type(self, auth, user):
        response = auth(user).post(
            "/resumes/", json=payload(section_order=["skill", "skill"])
        )

        assert response.status_code == 422

    def test_rejects_an_unknown_section_type(self, auth, user):
        response = auth(user).post(
            "/resumes/", json=payload(section_order=["personal_info"])
        )

        assert response.status_code == 422

    def test_links_the_callers_personal_info(self, auth, user, make_personal_info):
        personal_info = make_personal_info(user)

        response = auth(user).post(
            "/resumes/", json=payload(personal_info_id=str(personal_info.id))
        )

        assert response.status_code == 201
        assert response.json()["personal_info_id"] == str(personal_info.id)

    def test_refuses_someone_elses_personal_info(
        self, auth, user, other_user, make_personal_info, db: Session
    ):
        personal_info = make_personal_info(other_user)

        response = auth(user).post(
            "/resumes/", json=payload(personal_info_id=str(personal_info.id))
        )

        assert response.status_code == 404
        assert resume_count(db) == 0


class TestGet:
    def test_lists_only_the_callers_resumes(self, auth, user, other_user, make_resume):
        mine = make_resume(user)
        make_resume(other_user, title="Theirs")

        response = auth(user).get("/resumes/")

        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [str(mine.id)]

    def test_reads_one_resume(self, auth, user, make_resume):
        resume = make_resume(user)

        response = auth(user).get(f"/resumes/{resume.id}")

        assert response.status_code == 200
        assert response.json()["title"] == resume.title

    def test_hides_another_users_resume(self, auth, user, other_user, make_resume):
        resume = make_resume(other_user)

        response = auth(user).get(f"/resumes/{resume.id}")

        assert response.status_code == 404


class TestEdit:
    def test_replaces_every_field(self, auth, user, make_resume, db: Session):
        resume = make_resume(user)

        response = auth(user).put(
            f"/resumes/{resume.id}",
            json=replacement(title="Renamed", section_order=["education"]),
        )

        assert response.status_code == 200
        stored = get_resume(db, resume.id)
        assert stored is not None
        assert stored.title == "Renamed"
        assert stored.section_order == ["education"]

    def test_clears_an_omitted_field(self, auth, user, make_resume, db: Session):
        resume = make_resume(user, full_name="Ada Lovelace")

        response = auth(user).put(f"/resumes/{resume.id}", json=payload())

        assert response.status_code == 200
        stored = get_resume(db, resume.id)
        assert stored is not None
        assert stored.full_name is None

    def test_cannot_edit_another_users_resume(
        self, auth, user, other_user, make_resume, db: Session
    ):
        resume = make_resume(other_user, title="Theirs")

        response = auth(user).put(f"/resumes/{resume.id}", json=replacement())

        assert response.status_code == 404
        stored = get_resume(db, resume.id)
        assert stored is not None
        assert stored.title == "Theirs"


class TestDelete:
    def test_deletes_the_resume(self, auth, user, make_resume, db: Session):
        resume = make_resume(user)

        response = auth(user).delete(f"/resumes/{resume.id}")

        assert response.status_code == 200
        assert get_resume(db, resume.id) is None

    def test_cascades_to_its_membership_rows(
        self, auth, user, make_resume, make_skill, attach_section, db: Session
    ):
        resume = make_resume(user)
        attach_section(resume, ResumeSectionType.SKILL, make_skill(user).id)

        auth(user).delete(f"/resumes/{resume.id}")

        assert membership(db, resume.id) == []

    def test_cannot_delete_another_users_resume(
        self, auth, user, other_user, make_resume, db: Session
    ):
        resume = make_resume(other_user)

        response = auth(user).delete(f"/resumes/{resume.id}")

        assert response.status_code == 404
        assert get_resume(db, resume.id) is not None


class TestReplaceSections:
    def test_attaches_sections_in_order(
        self, auth, user, make_resume, make_project, db: Session
    ):
        resume = make_resume(user)
        first = make_project(user, name="First")
        second = make_project(user, name="Second")

        response = auth(user).put(
            f"/resumes/{resume.id}/sections",
            json={
                "sections": [
                    {"section_type": "project", "section_id": str(second.id)},
                    {"section_type": "project", "section_id": str(first.id)},
                ]
            },
        )

        assert response.status_code == 200
        assert membership(db, resume.id) == [
            ("project", second.id, 0),
            ("project", first.id, 1),
        ]

    def test_positions_run_per_type(
        self, auth, user, make_resume, make_project, make_skill, db: Session
    ):
        resume = make_resume(user)
        project = make_project(user)
        skill = make_skill(user)

        auth(user).put(
            f"/resumes/{resume.id}/sections",
            json={
                "sections": [
                    {"section_type": "project", "section_id": str(project.id)},
                    {"section_type": "skill", "section_id": str(skill.id)},
                ]
            },
        )

        # each type's run starts again at zero rather than sharing one counter
        assert membership(db, resume.id) == [
            ("project", project.id, 0),
            ("skill", skill.id, 0),
        ]

    def test_replaces_rather_than_appends(
        self, auth, user, make_resume, make_project, attach_section, db: Session
    ):
        resume = make_resume(user)
        old = make_project(user, name="Old")
        new = make_project(user, name="New")
        attach_section(resume, ResumeSectionType.PROJECT, old.id)

        auth(user).put(
            f"/resumes/{resume.id}/sections",
            json={"sections": [{"section_type": "project", "section_id": str(new.id)}]},
        )

        assert membership(db, resume.id) == [("project", new.id, 0)]

    def test_an_empty_list_detaches_everything(
        self, auth, user, make_resume, make_project, attach_section, db: Session
    ):
        resume = make_resume(user)
        attach_section(resume, ResumeSectionType.PROJECT, make_project(user).id)

        response = auth(user).put(
            f"/resumes/{resume.id}/sections", json={"sections": []}
        )

        assert response.status_code == 200
        assert membership(db, resume.id) == []

    def test_rejects_a_section_listed_twice(
        self, auth, user, make_resume, make_project
    ):
        resume = make_resume(user)
        project = make_project(user)

        response = auth(user).put(
            f"/resumes/{resume.id}/sections",
            json={
                "sections": [
                    {"section_type": "project", "section_id": str(project.id)},
                    {"section_type": "project", "section_id": str(project.id)},
                ]
            },
        )

        assert response.status_code == 422

    def test_refuses_someone_elses_section(
        self, auth, user, other_user, make_resume, make_project, db: Session
    ):
        resume = make_resume(user)
        theirs = make_project(other_user)

        response = auth(user).put(
            f"/resumes/{resume.id}/sections",
            json={
                "sections": [{"section_type": "project", "section_id": str(theirs.id)}]
            },
        )

        assert response.status_code == 404
        assert membership(db, resume.id) == []

    def test_refuses_a_section_that_does_not_exist(
        self, auth, user, make_resume, db: Session
    ):
        resume = make_resume(user)

        response = auth(user).put(
            f"/resumes/{resume.id}/sections",
            json={"sections": [{"section_type": "skill", "section_id": str(uuid4())}]},
        )

        assert response.status_code == 404
        assert membership(db, resume.id) == []

    def test_appends_an_unordered_type_to_the_section_order(
        self, auth, user, make_resume, make_project, db: Session
    ):
        resume = make_resume(user, section_order=[ResumeSectionType.SKILL])
        project = make_project(user)

        auth(user).put(
            f"/resumes/{resume.id}/sections",
            json={
                "sections": [{"section_type": "project", "section_id": str(project.id)}]
            },
        )

        stored = get_resume(db, resume.id)
        assert stored is not None
        assert stored.section_order == ["skill", "project"]

    def test_reads_the_membership_back(
        self, auth, user, make_resume, make_project, attach_section
    ):
        resume = make_resume(user)
        project = make_project(user)
        attach_section(resume, ResumeSectionType.PROJECT, project.id)

        response = auth(user).get(f"/resumes/{resume.id}/sections")

        assert response.status_code == 200
        assert response.json()["sections"] == [
            {"section_type": "project", "section_id": str(project.id)}
        ]


class TestDocument:
    def test_returns_blocks_in_section_order(
        self,
        auth,
        user,
        make_resume,
        make_project,
        make_skill,
        make_education,
        attach_section,
    ):
        resume = make_resume(
            user,
            section_order=[
                ResumeSectionType.EDUCATION,
                ResumeSectionType.SKILL,
                ResumeSectionType.PROJECT,
            ],
        )
        attach_section(resume, ResumeSectionType.PROJECT, make_project(user).id)
        attach_section(resume, ResumeSectionType.SKILL, make_skill(user).id)
        attach_section(resume, ResumeSectionType.EDUCATION, make_education(user).id)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert response.status_code == 200
        assert [block["type"] for block in response.json()["sections"]] == [
            "education",
            "skill",
            "project",
        ]

    def test_orders_items_within_a_block_by_position(
        self, auth, user, make_resume, make_project, attach_section
    ):
        resume = make_resume(user)
        first = make_project(user, name="First")
        second = make_project(user, name="Second")
        attach_section(resume, ResumeSectionType.PROJECT, second.id, position=0)
        attach_section(resume, ResumeSectionType.PROJECT, first.id, position=1)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        block = response.json()["sections"][0]
        assert [item["name"] for item in block["items"]] == ["Second", "First"]

    def test_hydrates_bullet_points(
        self, auth, user, make_resume, make_expirence, attach_section
    ):
        resume = make_resume(user)
        expirence = make_expirence(user, bullets=("Shipped it", "Then shipped more"))
        attach_section(resume, ResumeSectionType.EXPERIENCE, expirence.id)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        block = response.json()["sections"][0]
        assert [bullet["text"] for bullet in block["items"][0]["bullet_points"]] == [
            "Shipped it",
            "Then shipped more",
        ]

    def test_omits_a_section_type_with_no_items(
        self, auth, user, make_resume, make_skill, attach_section
    ):
        resume = make_resume(user)
        attach_section(resume, ResumeSectionType.SKILL, make_skill(user).id)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert [block["type"] for block in response.json()["sections"]] == ["skill"]

    def test_omits_a_type_left_out_of_the_section_order(
        self, auth, user, make_resume, make_skill, make_project, attach_section
    ):
        resume = make_resume(user, section_order=[ResumeSectionType.SKILL])
        attach_section(resume, ResumeSectionType.SKILL, make_skill(user).id)
        attach_section(resume, ResumeSectionType.PROJECT, make_project(user).id)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        # attached but unordered, so it is hidden rather than rendered
        assert [block["type"] for block in response.json()["sections"]] == ["skill"]

    def test_includes_the_linked_personal_info(
        self, auth, user, make_resume, make_personal_info
    ):
        personal_info = make_personal_info(user, email="ada@example.com")
        resume = make_resume(user, personal_info=personal_info)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert response.json()["personal_info"]["email"] == "ada@example.com"

    def test_personal_info_is_null_when_unset(self, auth, user, make_resume):
        resume = make_resume(user)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert response.json()["personal_info"] is None

    def test_prefers_the_resumes_own_full_name(
        self, auth, user, make_resume, db: Session
    ):
        user.name = "Account Name"
        db.commit()
        resume = make_resume(user, full_name="Resume Name")

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert response.json()["full_name"] == "Resume Name"

    def test_falls_back_to_the_account_name(self, auth, user, make_resume, db: Session):
        user.name = "Account Name"
        db.commit()
        resume = make_resume(user, full_name=None)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert response.json()["full_name"] == "Account Name"

    def test_full_name_is_empty_when_neither_is_set(self, auth, user, make_resume):
        resume = make_resume(user, full_name=None)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert response.json()["full_name"] == ""

    def test_hides_another_users_document(self, auth, user, other_user, make_resume):
        resume = make_resume(other_user)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        assert response.status_code == 404

    def test_skips_a_section_deleted_out_from_under_the_resume(
        self, auth, user, make_resume, make_skill, attach_section, db: Session
    ):
        """A stale id must not surface as a bare heading."""
        resume = make_resume(user)
        skill = make_skill(user)
        attach_section(resume, ResumeSectionType.SKILL, skill.id)
        attach_section(resume, ResumeSectionType.SKILL, uuid4(), position=1)

        response = auth(user).get(f"/resumes/{resume.id}/document")

        block = response.json()["sections"][0]
        assert [item["id"] for item in block["items"]] == [str(skill.id)]


class TestDetachOnSectionDelete:
    @pytest.mark.parametrize(
        ("section_type", "path", "fixture_name"),
        [
            (ResumeSectionType.SKILL, "/skill", "make_skill"),
            (ResumeSectionType.PROJECT, "/project", "make_project"),
            (ResumeSectionType.EXPERIENCE, "/experience", "make_expirence"),
            (ResumeSectionType.EDUCATION, "/education", "make_education"),
        ],
    )
    def test_deleting_a_section_detaches_it_from_resumes(
        self,
        request,
        auth,
        user,
        make_resume,
        attach_section,
        db: Session,
        section_type,
        path,
        fixture_name,
    ):
        section = request.getfixturevalue(fixture_name)(user)
        resume = make_resume(user)
        attach_section(resume, section_type, section.id)

        response = auth(user).delete(f"{path}/{section.id}")

        assert response.status_code == 200
        assert membership(db, resume.id) == []


class TestCreateWithSections:
    """The editor builds a resume and its contents in one modal, so create
    accepts the membership list rather than forcing a second request."""

    def test_attaches_sections_given_at_create_time(
        self, auth, user, make_project, make_skill, db: Session
    ):
        project = make_project(user)
        skill = make_skill(user)

        response = auth(user).post(
            "/resumes/",
            json=payload(
                sections=[
                    {"section_type": "project", "section_id": str(project.id)},
                    {"section_type": "skill", "section_id": str(skill.id)},
                ]
            ),
        )

        assert response.status_code == 201
        resume_id = UUID(response.json()["id"])
        assert membership(db, resume_id) == [
            ("project", project.id, 0),
            ("skill", skill.id, 0),
        ]

    def test_creates_with_no_sections_when_none_are_given(
        self, auth, user, db: Session
    ):
        response = auth(user).post("/resumes/", json=payload())

        assert response.status_code == 201
        assert membership(db, UUID(response.json()["id"])) == []

    def test_refuses_someone_elses_section_at_create_time(
        self, auth, user, other_user, make_project, db: Session
    ):
        theirs = make_project(other_user)

        response = auth(user).post(
            "/resumes/",
            json=payload(
                sections=[{"section_type": "project", "section_id": str(theirs.id)}]
            ),
        )

        assert response.status_code == 404
        assert resume_count(db) == 0, "the resume was created despite a bad section"

    def test_orders_sections_as_the_request_lists_them(
        self, auth, user, make_project, db: Session
    ):
        first = make_project(user, name="First")
        second = make_project(user, name="Second")

        response = auth(user).post(
            "/resumes/",
            json=payload(
                sections=[
                    {"section_type": "project", "section_id": str(second.id)},
                    {"section_type": "project", "section_id": str(first.id)},
                ]
            ),
        )

        assert membership(db, UUID(response.json()["id"])) == [
            ("project", second.id, 0),
            ("project", first.id, 1),
        ]

    def test_the_read_carries_a_last_modified_timestamp(self, auth, user):
        """The resumes table renders it as a column."""
        response = auth(user).post("/resumes/", json=payload())

        assert response.json()["updated_at"]

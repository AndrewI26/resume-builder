"""The resume export script's naming and its choice of what to delete.

The compile path is the worker's, covered by test_compiler_worker; what is new
here is the filename derivation and the wipe. The wipe is the part worth
pinning down, since it removes files the user did not necessarily put there.
"""

from pathlib import Path

from scripts.export_resumes import existing_pdfs, filenames, slug


def test_slug_matches_the_download_name_the_endpoint_sends():
    assert slug("Software Engineer") == "software-engineer"
    assert slug("Back/End (2024)") == "back-end--2024"


def test_slug_falls_back_when_a_title_has_nothing_usable_in_it():
    assert slug("!!!") == "resume"
    assert slug("") == "resume"


def test_duplicate_titles_get_numbered_rather_than_overwriting_each_other():
    assert filenames(["Backend", "Backend", "Frontend", "Backend"]) == [
        "backend.pdf",
        "backend-2.pdf",
        "frontend.pdf",
        "backend-3.pdf",
    ]


def test_titles_that_differ_only_in_punctuation_still_collide():
    # both slug to "back-end"; without the counter the second would clobber the
    # first and the run would quietly export one file for two resumes
    assert filenames(["Back End", "Back/End"]) == ["back-end.pdf", "back-end-2.pdf"]


def test_only_pdfs_directly_in_the_directory_are_up_for_deletion(tmp_path: Path):
    (tmp_path / "old.pdf").write_bytes(b"%PDF-")
    (tmp_path / "SHOUTED.PDF").write_bytes(b"%PDF-")
    (tmp_path / "notes.txt").write_text("keep me")
    (tmp_path / "resume.tex").write_text("keep me too")

    nested = tmp_path / "archive"
    nested.mkdir()
    (nested / "buried.pdf").write_bytes(b"%PDF-")

    assert [path.name for path in existing_pdfs(tmp_path)] == ["SHOUTED.PDF", "old.pdf"]


def test_a_directory_named_like_a_pdf_is_not_deleted(tmp_path: Path):
    (tmp_path / "weird.pdf").mkdir()

    assert existing_pdfs(tmp_path) == []


def test_a_directory_that_does_not_exist_yet_has_nothing_to_delete(tmp_path: Path):
    assert existing_pdfs(tmp_path / "not-created-yet") == []

"""The LaTeX serializer.

The golden fixture is the same file the browser serializer was tested against,
so this is also the check that the port did not change what gets typeset.
"""

import json
from pathlib import Path

import pytest

from schemas.bullet_point import BulletPoint
from schemas.resume import ResumeDocument
from services.latex.escape import escape_latex, escape_latex_url, render_bullet
from services.latex.preamble import PREAMBLE
from services.latex.serialize import serialize_to_tex

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def sample() -> ResumeDocument:
    return ResumeDocument.model_validate(
        json.loads((FIXTURES / "sample_document.json").read_text())
    )


def document(**overrides: object) -> ResumeDocument:
    base: dict[str, object] = {
        "id": "00000000-0000-0000-0000-000000000001",
        "title": "Untitled",
        "template": "jakes",
        "full_name": "Ada Lovelace",
        "personal_info": None,
        "sections": [],
    }
    return ResumeDocument.model_validate(base | overrides)


def body(tex: str) -> str:
    """Just the generated part.

    The preamble defines the very macros the body calls, so a bare substring
    search over the whole document would match ``\\newcommand`` definitions and
    pass regardless of what was generated.
    """
    return tex[len(PREAMBLE) :]


class TestGoldenFile:
    def test_reproduces_the_checked_in_expected_output(self, sample: ResumeDocument):
        assert serialize_to_tex(sample) == (FIXTURES / "expected.tex").read_text()


class TestDocumentStructure:
    def test_opens_with_the_frozen_preamble(self):
        assert serialize_to_tex(document()).startswith(PREAMBLE)

    def test_closes_the_document(self):
        assert serialize_to_tex(document()).endswith("\\end{document}\n")

    def test_drops_a_block_with_no_items(self):
        tex = serialize_to_tex(document(sections=[{"type": "skill", "items": []}]))

        assert "\\section{Skills}" not in body(tex)


def center_block(tex: str) -> str:
    """The header's ``center`` environment, braces included."""
    start = tex.index("\\begin{center}")
    return tex[start : tex.index("\\end{center}", start) + len("\\end{center}")]


class TestHeader:
    def test_a_name_with_contact_details_breaks_the_line_after_it(self):
        info = {"id": "50000000-0000-0000-0000-0000000000ff", "email": "ada@x.com"}
        block = center_block(serialize_to_tex(document(personal_info=info)))

        assert "{\\Huge \\scshape Ada Lovelace} \\\\ \\vspace{1pt}" in block

    def test_a_name_with_no_contact_details_does_not_end_the_block_on_a_break(self):
        # a trailing "\\" with nothing after it is the fatal LaTeX error
        # "There's no line here to end", which fails the whole compile
        block = center_block(serialize_to_tex(document(personal_info=None)))

        assert "{\\Huge \\scshape Ada Lovelace}" in block
        assert "\\\\" not in block

    def test_neither_a_name_nor_contact_details_leaves_the_block_empty(self):
        block = center_block(
            serialize_to_tex(document(full_name="", personal_info=None))
        )

        assert block == "\\begin{center}\n\\end{center}"


class TestEscaping:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("50%", "50\\%"),
            ("A&B", "A\\&B"),
            ("cost $5", "cost \\$5"),
            ("a_b", "a\\_b"),
            ("#1", "\\#1"),
            ("{x}", "\\{x\\}"),
            ("~", "\\textasciitilde{}"),
            ("^", "\\textasciicircum{}"),
        ],
    )
    def test_escapes_the_special_characters(self, raw: str, expected: str):
        assert escape_latex(raw) == expected

    def test_escapes_a_backslash_without_re_escaping_its_own_braces(self):
        assert escape_latex("a\\b") == "a\\textbackslash{}b"

    def test_percent_encodes_a_url_rather_than_backslash_escaping_it(self):
        assert escape_latex_url("https://x.com/a~b") == "https://x.com/a%7Eb"

    def test_leaves_an_existing_escape_sequence_alone(self):
        assert escape_latex_url("https://x.com/a%20b") == "https://x.com/a%20b"

    def test_encodes_a_stray_percent(self):
        assert escape_latex_url("https://x.com/100%") == "https://x.com/100%25"

    def test_a_name_with_a_special_character_reaches_the_header_escaped(self):
        tex = serialize_to_tex(document(full_name="Ada & Co"))

        assert "{\\Huge \\scshape Ada \\& Co}" in body(tex)


class TestBullets:
    def test_wraps_a_bolded_range(self):
        bullet = BulletPoint(text="Shipped it", bolded=[(0, 6)])

        assert render_bullet(bullet) == "\\textbf{Shipped} it"

    def test_escapes_inside_and_outside_the_bold_run(self):
        bullet = BulletPoint(text="A&B and C&D", bolded=[(0, 2)])

        assert render_bullet(bullet) == "\\textbf{A\\&B} and C\\&D"

    def test_offsets_are_taken_before_escaping_lengthens_the_text(self):
        # "&" becomes "\\&": escaping first would slide the bold one character
        bullet = BulletPoint(text="&& ok", bolded=[(3, 4)])

        assert render_bullet(bullet) == "\\&\\& \\textbf{ok}"

    def test_a_plain_bullet_is_left_unwrapped(self):
        assert render_bullet(BulletPoint(text="plain", bolded=[])) == "plain"

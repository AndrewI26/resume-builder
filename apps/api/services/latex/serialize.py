"""``ResumeDocument`` -> Jake's Resume LaTeX source.

A pure function with no I/O, which is the point: where the resulting ``.tex``
gets compiled stays a swappable decision rather than an architectural one.

This is a port of the browser serializer it replaced, kept deliberately
line-for-line with it. ``tests/test_latex_serialize.py`` compares the output
against the same checked-in fixture the TypeScript tests use, so the two cannot
drift apart silently while both exist.
"""

from schemas.bullet_point import BulletPoint
from schemas.education import EducationRead
from schemas.expirence import ExpirenceRead
from schemas.link import Link
from schemas.personal_info import PersonalInfoRead
from schemas.project import ProjectRead
from schemas.resume import (
    EducationBlock,
    ExperienceBlock,
    ProjectBlock,
    ResumeDocument,
    SectionBlock,
    SkillBlock,
)
from schemas.skill import SkillRead
from services.latex.escape import escape_latex, escape_latex_url, render_bullet
from services.latex.preamble import PREAMBLE


def _href(url: str, body: str) -> str:
    return rf"\href{{{escape_latex_url(url)}}}{{{body}}}"


def _underlined(label: str) -> str:
    r"""Underline a contact label so the rule lands in the same place every time.

    ``\underline`` puts its rule below the *depth* of what it is given, and
    depth depends on the characters present: ``Portfolio`` has no descenders
    and rides high, while ``github.com/...`` has a ``g``, a ``j`` and a ``/`` —
    all of which descend in Computer Modern — and sits nearly 2pt lower. Left
    alone the contact line underlines form a visible staircase.

    ``\smash`` drops the label's own height and depth, and the phantom then
    imposes one fixed set taken from the deepest characters that show up in a
    URL. The result no longer depends on what the text happens to spell.
    """
    return rf"\underline{{\smash{{{label}}}\vphantom{{gj/}}}}"


def _contact(icon: str, label: str, url: str | None = None) -> str:
    """A contact line entry: an icon, then linked or plain text."""
    body = rf"\raisebox{{-0.2\height}}\{icon}\ {_underlined(label)}"
    return body if url is None else _href(url, body)


def _display_url(url: str) -> str:
    """Strip the scheme and any trailing slash, the way the template prints links."""
    without_scheme = url.removeprefix("https://").removeprefix("http://")
    return escape_latex(without_scheme.removesuffix("/"))


def _link_label(link: Link, fallback: str) -> str:
    """A link's custom label if it has one, otherwise a fallback."""
    return escape_latex(link.label) if link.label else fallback


def _render_header(full_name: str, info: PersonalInfoRead | None) -> str:
    entries: list[str] = []

    if info is not None:
        if info.phone_number:
            entries.append(_contact("faPhone", escape_latex(info.phone_number)))
        if info.email:
            entries.append(
                _contact("faEnvelope", escape_latex(info.email), f"mailto:{info.email}")
            )
        if info.linkedin:
            label = _link_label(info.linkedin, _display_url(info.linkedin.url))
            entries.append(_contact("faLinkedin", label, info.linkedin.url))
        if info.github:
            label = _link_label(info.github, _display_url(info.github.url))
            entries.append(_contact("faGithub", label, info.github.url))
        if info.portfolio:
            label = _link_label(info.portfolio, "Portfolio")
            entries.append(_contact("faInternetExplorer", label, info.portfolio.url))
        if info.address:
            entries.append(_contact("faMapMarker", escape_latex(info.address)))

    return "\n".join(
        [
            r"\begin{center}",
            rf"    {{\Huge \scshape {escape_latex(full_name)}}} \\ \vspace{{1pt}}",
            *(f"    {entry} ~" for entry in entries),
            r"\end{center}",
        ]
    )


def _render_skills(items: list[SkillRead]) -> str:
    lines = [
        rf"     \textbf{{{escape_latex(skill.name)}}}{{: "
        rf"{escape_latex(', '.join(skill.items))} }}"
        for skill in items
    ]

    return "\n".join(
        [
            r"\section{Skills}",
            r" \begin{itemize}[leftmargin=0.15in, label={}]",
            r"    \small{\item{",
            # the separator goes between lines, never after the last one
            " \\\\\n".join(lines) + " }}",
            r" \end{itemize}",
            r" \vspace{-20pt}",
        ]
    )


def _render_bullets(bullets: list[BulletPoint]) -> list[str]:
    if not bullets:
        return []

    return [
        r"      \resumeItemListStart",
        *(rf"         \resumeItem{{{render_bullet(bullet)}}}" for bullet in bullets),
        r"      \resumeItemListEnd",
    ]


def _render_experience(items: list[ExpirenceRead]) -> str:
    entries: list[str] = []
    for experience in items:
        entries += [
            r"    \resumeSubheading",
            (
                rf"        {{\textbf{{{escape_latex(experience.company)}}}}}"
                rf"{{{escape_latex(experience.duration)}}}"
            ),
            (
                rf"      {{{escape_latex(experience.position)}}} "
                rf"{{{escape_latex(experience.location)}}}"
            ),
            *_render_bullets(experience.bullet_points),
            "",
        ]

    return "\n".join(
        [
            r"\section{Experience}",
            r"  \resumeSubHeadingListStart",
            *entries,
            r"  \resumeSubHeadingListEnd",
            r"\vspace{-16pt}",
        ]
    )


def _render_projects(items: list[ProjectRead]) -> str:
    entries: list[str] = []
    for index, project in enumerate(items):
        name = rf"\textbf{{{escape_latex(project.name)}}}"
        # a linked project gets a chain glyph after the name
        title = (
            f"{name} {_href(project.link, chr(92) + 'faLink')}"
            if project.link
            else name
        )
        technologies = (
            rf" $|$ \emph{{ {escape_latex(', '.join(project.technologies))} }}"
            if project.technologies
            else ""
        )

        entries += [
            r"      \resumeProjectHeading",
            rf"          {{{title}{technologies}}}{{}}",
            *_render_bullets(project.bullet_points),
            # tightens the gap between entries, but not before the list ends
            *([] if index == len(items) - 1 else [r"          \vspace{-16pt}", ""]),
        ]

    return "\n".join(
        [
            r"\section{Projects}",
            r"    \vspace{-5pt}",
            r"    \resumeSubHeadingListStart",
            *entries,
            r"    \resumeSubHeadingListEnd",
        ]
    )


def _render_education(items: list[EducationRead]) -> str:
    entries: list[str] = []
    for education in items:
        entries += [
            r"  \resumeSubheading",
            (
                rf"      {{{escape_latex(education.name)}}}"
                rf"{{{escape_latex(education.duration)}}}"
            ),
            (
                rf"      {{{escape_latex(education.subheading)}}} "
                rf"{{{escape_latex(education.location)}}}"
            ),
            "",
        ]

    return "\n".join(
        [
            r"\section{Education}",
            r"  \resumeSubHeadingListStart",
            *entries,
            r"  \resumeSubHeadingListEnd",
        ]
    )


def _render_block(block: SectionBlock) -> str:
    match block:
        case SkillBlock():
            return _render_skills(block.items)
        case ExperienceBlock():
            return _render_experience(block.items)
        case ProjectBlock():
            return _render_projects(block.items)
        case EducationBlock():
            return _render_education(block.items)


def serialize_to_tex(document: ResumeDocument) -> str:
    """Build the complete ``.tex`` source for a resume document."""
    # the API drops empty blocks, but a bare heading is ugly enough to guard
    # against twice
    body = [_render_block(block) for block in document.sections if block.items]

    return "\n".join(
        [
            PREAMBLE,
            "",
            _render_header(document.full_name, document.personal_info),
            "",
            *(line for section in body for line in (section, "")),
            r"\end{document}",
            "",
        ]
    )

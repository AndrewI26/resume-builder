"""Turning user text into LaTeX source.

Every string that reaches the template goes through here first. Missing an
escape does not merely look wrong — a stray ``\\`` or ``%`` in a name silently
changes what the rest of the document means, or fails the compile outright.
"""

import re
from typing import NamedTuple

from schemas.bullet_point import BulletPoint

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "%": r"\%",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_SPECIAL = re.compile(r"[\\{}$&#_%~^]")


def escape_latex(value: str) -> str:
    """Escape the ten characters LaTeX treats specially.

    Done in a single pass on purpose: escaping ``\\`` first would produce a
    ``\\textbackslash{}`` whose own braces a later pass would then escape again.
    """
    return _SPECIAL.sub(lambda match: _ESCAPES[match.group()], value)


_URL_ENCODES = {
    "\\": "%5C",
    "{": "%7B",
    "}": "%7D",
    "$": "%24",
    "&": "%26",
    "#": "%23",
    "_": "%5F",
    "^": "%5E",
    "~": "%7E",
    "%": "%25",
}

_URL_SPECIAL = re.compile(r"[\\{}$&#_^~]|%(?![0-9A-Fa-f]{2})")


def escape_latex_url(url: str) -> str:
    """Make a URL safe as the target of ``\\href``.

    Backslash escaping is not an option here. Jake's template calls ``\\href``
    from inside other macros' arguments, where hyperref cannot apply its
    verbatim catcodes, so ``~`` would expand to a non-breaking space and change
    the address. Percent-encoding sidesteps the catcodes entirely and means the
    same thing to a browser.

    A ``%`` that already introduces a valid escape sequence is left alone, so a
    pre-encoded URL survives the trip rather than becoming ``%2520``.
    """
    return _URL_SPECIAL.sub(lambda match: _URL_ENCODES[match.group()], url)


class Segment(NamedTuple):
    """One run of a bullet's text, either bold or plain."""

    text: str
    bold: bool


def split_bullet(bullet: BulletPoint) -> list[Segment]:
    """Walk a bullet's text into alternating plain and bold segments.

    ``bolded`` ranges are inclusive on both ends. The schema guarantees they
    arrive sorted and disjoint; the sort and the ``start < cursor`` skip here
    mean a bad payload degrades to dropped bolding rather than overlapping
    output.
    """
    segments: list[Segment] = []
    cursor = 0

    for start, end in sorted(bullet.bolded):
        if start < cursor or start > end or start < 0:
            continue

        if start > cursor:
            segments.append(Segment(bullet.text[cursor:start], bold=False))

        # ``end`` is inclusive, so the slice has to reach one past it
        segments.append(Segment(bullet.text[start : end + 1], bold=True))
        cursor = end + 1

    if cursor < len(bullet.text):
        segments.append(Segment(bullet.text[cursor:], bold=False))

    return segments


def render_bullet(bullet: BulletPoint) -> str:
    """Render one bullet point, wrapping its bolded ranges in ``\\textbf``.

    Each segment is escaped on its own and only then wrapped. Escaping the
    whole string up front would shift every offset — a name containing ``&``
    becomes two characters longer — and the bolding would land in the wrong
    place.
    """
    return "".join(
        rf"\textbf{{{escape_latex(segment.text)}}}"
        if segment.bold
        else escape_latex(segment.text)
        for segment in split_bullet(bullet)
    )

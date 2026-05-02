"""Jinja2-based LaTeX resume renderer."""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Characters that must be escaped in LaTeX
_LATEX_SPECIAL = re.compile(r'([&%$#_{}~^\\])')
_LATEX_REPLACEMENTS = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def _latex_escape(value: str) -> str:
    if not isinstance(value, str):
        return value
    return _LATEX_SPECIAL.sub(lambda m: _LATEX_REPLACEMENTS[m.group()], value)


def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape([]),  # LaTeX — no HTML escaping
        keep_trailing_newline=True,
    )
    env.filters["latex_escape"] = _latex_escape
    return env


_env = _make_env()


def render_resume(context: dict) -> str:
    """Render resume.tex.j2 with the given context and return LaTeX source."""
    template = _env.get_template("resume.tex.j2")
    return template.render(**context)

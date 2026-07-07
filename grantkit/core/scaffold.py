"""Scaffold a new grant project (``grantkit init``).

Produces the unified 0.2.0 layout that the rest of the engine reads:

* ``grant.yaml`` — funder / program / deadline plus the section table
  (``id``/``title``/``word_limit``/``char_limit``/``page_limit``/``required``/
  ``file``).
* ``responses/<id>.md`` — one stub per section.
* ``budget.yaml`` — an empty, arithmetically-consistent budget skeleton.
* ``references.bib`` — an empty BibTeX file.

When ``--funder PACK_ID`` is given, sections and portal/locale defaults come
from the funder rule pack; otherwise a small generic skeleton is written.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from ..packs import FunderPack, resolve_pack

PLACEHOLDER = "[TO BE COMPLETED]"

_GENERIC_SECTIONS = [
    {
        "id": "summary",
        "title": "Project Summary",
        "word_limit": 250,
        "char_limit": None,
        "page_limit": None,
        "required": True,
        "file": "responses/summary.md",
    },
    {
        "id": "narrative",
        "title": "Project Narrative",
        "word_limit": 1500,
        "char_limit": None,
        "page_limit": None,
        "required": True,
        "file": "responses/narrative.md",
    },
]


class ScaffoldError(Exception):
    """Raised when a project cannot be scaffolded."""


def init_project(
    root: Path,
    funder: Optional[str] = None,
    *,
    force: bool = False,
) -> list[Path]:
    """Scaffold a grant project under ``root``.

    Returns the list of files created. Raises :class:`ScaffoldError` if
    ``grant.yaml`` already exists and ``force`` is false, or if ``funder`` does
    not resolve to a known pack.
    """
    root = Path(root)
    grant_path = root / "grant.yaml"
    if grant_path.exists() and not force:
        raise ScaffoldError(
            f"{grant_path} already exists; pass --force to overwrite."
        )

    pack: Optional[FunderPack] = None
    if funder:
        pack = resolve_pack(funder)
        if pack is None:
            from ..packs import list_pack_ids

            raise ScaffoldError(
                f"Unknown funder pack '{funder}'. Available: "
                f"{', '.join(list_pack_ids()) or '(none)'}"
            )

    sections = _sections_for(pack)
    config = _grant_config(pack, sections)

    created: list[Path] = []
    root.mkdir(parents=True, exist_ok=True)

    grant_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    created.append(grant_path)

    accepts_markdown = pack.accepts_markdown if pack else True
    responses_dir = root / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    for section in sections:
        section_path = root / section["file"]
        section_path.parent.mkdir(parents=True, exist_ok=True)
        if section_path.exists() and not force:
            continue
        section_path.write_text(
            _section_stub(section, accepts_markdown=accepts_markdown),
            encoding="utf-8",
        )
        created.append(section_path)

    budget_path = root / "budget.yaml"
    if force or not budget_path.exists():
        budget_path.write_text(_budget_stub(pack), encoding="utf-8")
        created.append(budget_path)

    references_path = root / "references.bib"
    if force or not references_path.exists():
        references_path.write_text(
            "% GrantKit references. Add BibTeX entries here and cite them\n"
            "% from responses with [@key].\n",
            encoding="utf-8",
        )
        created.append(references_path)

    return created


def _sections_for(pack: Optional[FunderPack]) -> list[dict]:
    if pack and pack.sections:
        out = []
        for section in pack.sections:
            file_rel = section.file or f"responses/{section.id}.md"
            out.append(
                {
                    "id": section.id,
                    "title": section.title,
                    "word_limit": section.word_limit,
                    "char_limit": section.char_limit,
                    "page_limit": section.page_limit,
                    "required": section.required,
                    "file": file_rel,
                }
            )
        return out
    return [dict(section) for section in _GENERIC_SECTIONS]


def _grant_config(pack: Optional[FunderPack], sections: list[dict]) -> dict:
    config: dict = {
        "title": "",
        "funder": pack.name if pack else "",
        "program": (pack.program if pack else "") or "",
        "deadline": "",
    }
    if pack:
        config["pack"] = pack.id
    config["accepts_markdown"] = pack.accepts_markdown if pack else True
    config["locale"] = pack.locale if pack else "en-US"
    config["references"] = "references.bib"
    config["budget"] = "budget.yaml"
    config["sections"] = sections
    return config


def _section_stub(section: dict, *, accepts_markdown: bool = True) -> str:
    """A per-section stub.

    Frontmatter is stripped before linting, so it is always safe. The body,
    however, is linted: for plain-text portals we omit the Markdown ``#``
    heading so a freshly scaffolded project does not fail its own
    plain-text check.
    """
    lines = ["---", f"title: {section['title']}"]
    if section.get("word_limit"):
        lines.append(f"word_limit: {section['word_limit']}")
    if section.get("char_limit"):
        lines.append(f"char_limit: {section['char_limit']}")
    if section.get("page_limit"):
        lines.append(f"page_limit: {section['page_limit']}")
    lines.append("status: draft")
    lines.append("---")
    lines.append("")
    if accepts_markdown:
        lines.append(f"# {section['title']}")
        lines.append("")
    lines.append(PLACEHOLDER)
    lines.append("")
    return "\n".join(lines)


def _budget_stub(pack: Optional[FunderPack]) -> str:
    rate = 0.0
    note = ""
    if pack and pack.budget_rules and pack.budget_rules.currency:
        note = f"# Currency: {pack.budget_rules.currency}\n"
    skeleton = {
        "years_in_budget": 1,
        "personnel": {"senior_key": [], "other": []},
        "fringe_benefits": {"rate": rate},
        "equipment": [],
        "travel": {"domestic": [], "foreign": []},
        "participant_support": [],
        "other_direct_costs": [],
        "indirect_costs": {"rate": rate},
    }
    header = (
        "# GrantKit budget. Line items feed `grantkit check` (arithmetic +\n"
        "# funder caps). See docs/artifacts.md for the schema.\n"
    )
    body: str = yaml.safe_dump(skeleton, sort_keys=False)
    return header + note + body

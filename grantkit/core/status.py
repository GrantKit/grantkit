"""Build the ``status.json`` document.

``status.json`` is GrantKit's public, machine-readable contract. It is emitted
by ``grantkit status --json`` and always by ``grantkit build``. External
consumers (e.g. the PolicyEngine/CRM viewing surface) depend on this exact
shape, which is documented in ``docs/artifacts.md``.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .. import __version__
from .checks import CheckResult, run_checks

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .project import GrantProject


def build_status(
    project: "GrantProject",
    checks: Optional[CheckResult] = None,
    *,
    check_urls: bool = False,
) -> dict:
    """Assemble the full ``status.json`` payload for ``project``.

    If ``checks`` is not supplied the linter is run (without the network URL
    check unless ``check_urls`` is set).
    """
    if checks is None:
        checks = run_checks(project, check_urls=check_urls)

    sections = [
        {
            "id": section.id,
            "title": section.title,
            "words": section.words,
            "word_limit": section.word_limit,
            "status": section.status,
            "issues": list(section.issues),
        }
        for section in project.sections
    ]

    return {
        "grantkit_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grant": {
            "title": project.title,
            "funder": project.funder,
            "program": project.program,
            "deadline": project.deadline or "",
        },
        "completion": {
            "sections_total": project.sections_total,
            "sections_complete": project.sections_complete,
            "words_total": project.total_words,
            "percent": project.completion_percent,
        },
        "sections": sections,
        "checks": checks.to_dict(),
    }


def write_status(
    project: "GrantProject",
    checks: Optional[CheckResult] = None,
    *,
    path: Optional[Path] = None,
    check_urls: bool = False,
) -> Path:
    """Write ``status.json`` to the project root and return its path."""
    status = build_status(project, checks, check_urls=check_urls)
    out_path = path or (project.root / "status.json")
    out_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return out_path


def days_until_deadline(deadline: Optional[str]) -> Optional[int]:
    """Whole days from today until ``deadline`` (negative if past).

    Returns ``None`` when the deadline is missing or unparseable.
    """
    if not deadline:
        return None
    try:
        due = date.fromisoformat(str(deadline)[:10])
    except ValueError:
        return None
    return (due - date.today()).days

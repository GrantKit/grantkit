"""Build a structured review packet (``grantkit review``).

The packet bundles everything an AI agent needs to critique a proposal — the
funder's assessment rubric (from the rule pack), the assembled section content,
and the current lint findings — as one JSON object. GrantKit makes **no** AI
calls itself; it only assembles the packet for an agent to consume.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from .. import __version__
from .checks import CheckResult, run_checks

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .project import GrantProject


def build_review(
    project: "GrantProject",
    *,
    include_pack: bool = False,
    checks: Optional[CheckResult] = None,
) -> dict:
    """Assemble the review packet for ``project``.

    ``include_pack`` (``grantkit review --pack``) embeds the complete funder
    rule pack — all formatting rules, budget rules, and portal quirks — not
    just the assessment rubric.
    """
    if checks is None:
        checks = run_checks(project)

    pack = project.pack
    rubric = []
    if pack:
        rubric = [
            {
                "id": crit.id,
                "name": crit.name,
                "description": crit.description,
                "citation": crit.citation,
                "url": crit.url,
            }
            for crit in pack.review_rubric
        ]

    sections = [
        {
            "id": section.id,
            "title": section.title,
            "words": section.words,
            "word_limit": section.word_limit,
            "status": section.status,
            "body": section.body if section.exists else "",
        }
        for section in project.sections
    ]

    packet = {
        "grantkit_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grant": {
            "title": project.title,
            "funder": project.funder,
            "program": project.program,
            "deadline": project.deadline or "",
        },
        "rubric": rubric,
        "sections": sections,
        "checks": checks.to_dict(),
    }

    if include_pack and pack is not None:
        packet["pack"] = pack.raw or {
            "id": pack.id,
            "name": pack.name,
            "program": pack.program,
            "locale": pack.locale,
        }

    return packet

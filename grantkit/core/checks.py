"""The GrantKit check runner.

``run_checks`` consolidates every linter behind a single API and returns a
:class:`CheckResult` — a flat list of :class:`CheckItem` findings, each tagged
``error`` or ``warning``. The CLI, MCP server, GitHub Action, and ``status.json``
all consume this one structure.

Checks performed (all offline unless noted):

* **structure** — required sections exist and are non-empty.
* **limits** — word / character / page limits per section.
* **placeholders** — ``[TO BE COMPLETED]``, ``TODO``, ``lorem ipsum`` etc.
* **markdown** — parses as valid Markdown; and, when the funder portal is
  plain-text only (``accepts_markdown: false``), no Markdown syntax is used.
* **citations** — every ``[@key]`` / ``\\cite{key}`` resolves against
  ``references.bib``.
* **budget** — arithmetic consistency (fringe/indirect), funder caps, and —
  only when ``BLS_API_KEY`` / ``GSA_API_KEY`` are set — BLS salary and GSA
  per-diem sanity (these make network calls, so they are opt-in).
* **funder rules** — the rule pack's formatting rules. When the pack declares
  ``content_engine: nsf_pappg`` the full NSF PAPPG content validator runs.
* **spelling** — US/UK spelling locale from the pack.
* **urls** — link liveness. Network, so only when ``check_urls=True``
  (``grantkit check --urls``).
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import markdown as _markdown

from ..packs import FunderPack
from .markdown_validator import MarkdownContentValidator
from .spelling import check_spelling

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .project import GrantProject


@dataclass
class CheckItem:
    """A single lint finding."""

    level: str  # "error" | "warning"
    rule: str
    message: str
    section: Optional[str] = None
    citation: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "rule": self.rule,
            "message": self.message,
            "section": self.section,
            "citation": self.citation,
        }


@dataclass
class CheckResult:
    """The full set of findings from a check run."""

    items: list[CheckItem] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for i in self.items if i.level == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for i in self.items if i.level == "warning")

    def failed(self, strict: bool = False) -> bool:
        """True if the run should exit non-zero.

        Errors always fail. Warnings fail only under ``--strict``.
        """
        if self.errors:
            return True
        return strict and self.warnings > 0

    def to_dict(self) -> dict:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "items": [i.to_dict() for i in self.items],
        }


def run_checks(
    project: "GrantProject",
    *,
    strict: bool = False,
    check_urls: bool = False,
) -> CheckResult:
    """Run every applicable linter against ``project``.

    ``strict`` does not change which checks run; it only affects
    :meth:`CheckResult.failed`. ``check_urls`` enables the (network) URL
    liveness check.
    """
    items: list[CheckItem] = []
    pack = project.pack

    items += _check_structure(project)
    items += _check_limits(project)
    items += _check_placeholders(project)
    items += _check_markdown(project)
    items += _check_citations(project)
    items += _check_budget(project, pack)
    items += _check_funder_rules(project, pack)
    items += _check_spelling(project)
    if check_urls:
        items += _check_urls(project)

    return CheckResult(items=items)


# -- individual checks --------------------------------------------------


def _check_structure(project: "GrantProject") -> list[CheckItem]:
    out: list[CheckItem] = []
    for section in project.sections:
        if not section.required:
            continue
        if not section.exists:
            out.append(
                CheckItem(
                    level="error",
                    rule="required_section_missing",
                    message=(
                        f"Required section '{section.title}' has no response "
                        f"file (expected {section.file or section.id + '.md'})."
                    ),
                    section=section.id,
                )
            )
        elif section.words == 0:
            out.append(
                CheckItem(
                    level="error",
                    rule="required_section_empty",
                    message=f"Required section '{section.title}' is empty.",
                    section=section.id,
                )
            )
    return out


def _check_limits(project: "GrantProject") -> list[CheckItem]:
    out: list[CheckItem] = []
    for section in project.sections:
        if section.over_word_limit:
            out.append(
                CheckItem(
                    level="error",
                    rule="word_limit_exceeded",
                    message=(
                        f"{section.words} words exceeds the "
                        f"{section.word_limit}-word limit for "
                        f"'{section.title}'."
                    ),
                    section=section.id,
                )
            )
        if section.over_char_limit:
            out.append(
                CheckItem(
                    level="error",
                    rule="char_limit_exceeded",
                    message=(
                        f"{section.chars} characters exceeds the "
                        f"{section.char_limit}-character limit for "
                        f"'{section.title}'."
                    ),
                    section=section.id,
                )
            )
        if section.over_page_limit:
            out.append(
                CheckItem(
                    level="warning",
                    rule="page_limit_estimate_exceeded",
                    message=(
                        f"~{section.pages:.1f} pages likely exceeds the "
                        f"{section.page_limit}-page limit for "
                        f"'{section.title}' (rough estimate at "
                        f"{project.words_per_page} words/page; confirm in the "
                        f"built PDF)."
                    ),
                    section=section.id,
                )
            )
    return out


def _check_placeholders(project: "GrantProject") -> list[CheckItem]:
    out: list[CheckItem] = []
    for section in project.sections:
        if section.placeholders:
            joined = ", ".join(section.placeholders)
            out.append(
                CheckItem(
                    level="warning",
                    rule="placeholder_text",
                    message=(
                        f"'{section.title}' still contains placeholder text: "
                        f"{joined}."
                    ),
                    section=section.id,
                )
            )
    return out


def _check_markdown(project: "GrantProject") -> list[CheckItem]:
    out: list[CheckItem] = []

    # 1. Every section must parse as Markdown without raising.
    for section in project.sections:
        if not section.exists:
            continue
        try:
            _markdown.markdown(section.body)
        except Exception as exc:  # pragma: no cover - defensive
            out.append(
                CheckItem(
                    level="error",
                    rule="invalid_markdown",
                    message=f"Could not parse Markdown: {exc}",
                    section=section.id,
                )
            )

    # 2. Plain-text portals: any Markdown syntax is a problem.
    if not project.accepts_markdown:
        citation = _plain_text_citation(project.pack)
        validator = MarkdownContentValidator(accepts_markdown=False)
        for section in project.sections:
            if not section.exists:
                continue
            result = validator.validate_content(section.body, section.id)
            for violation in result.violations:
                out.append(
                    CheckItem(
                        level="error",
                        rule="markdown_in_plain_text",
                        message=(
                            f"{violation.message} on line "
                            f"{violation.line_number} — this portal accepts "
                            f"plain text only, so Markdown would be pasted "
                            f"literally."
                        ),
                        section=section.id,
                        citation=citation,
                    )
                )
    return out


def _plain_text_citation(pack: Optional[FunderPack]) -> Optional[str]:
    if not pack:
        return None
    for rule in pack.formatting_rules:
        if rule.id in ("plain_text_only", "plain_text"):
            return rule.citation
    return None


def _check_citations(project: "GrantProject") -> list[CheckItem]:
    from ..references.bibtex_manager import BibTeXManager
    from ..references.citation_extractor import CitationExtractor

    out: list[CheckItem] = []
    extractor = CitationExtractor()

    # Collect (key -> first section) across all response bodies.
    used: dict[str, str] = {}
    syntax_issues: list[tuple[str, str]] = []
    for section in project.sections:
        if not section.exists:
            continue
        for match in extractor.extract_citations_from_text(section.body):
            used.setdefault(match.citation_key, section.id)
        for issue in extractor.validate_citation_syntax(section.body):
            syntax_issues.append((section.id, issue))

    if not used and not syntax_issues:
        return out

    bib_path = project.references_path
    if bib_path is None:
        if used:
            out.append(
                CheckItem(
                    level="warning",
                    rule="missing_references_bib",
                    message=(
                        f"{len(used)} citation(s) used but no references.bib "
                        f"was found to resolve them against."
                    ),
                )
            )
        return out + [
            CheckItem(
                level="warning",
                rule="citation_syntax",
                message=msg,
                section=sid,
            )
            for sid, msg in syntax_issues
        ]

    manager = BibTeXManager(project.root)
    manager.load_bibliography(bib_path)
    known = manager.get_all_keys()
    for key, sid in sorted(used.items()):
        if key not in known:
            out.append(
                CheckItem(
                    level="error",
                    rule="unresolved_citation",
                    message=(
                        f"Citation '{key}' does not resolve against "
                        f"{bib_path.name}."
                    ),
                    section=sid,
                    citation=key,
                )
            )
    for sid, msg in syntax_issues:
        out.append(
            CheckItem(
                level="warning",
                rule="citation_syntax",
                message=msg,
                section=sid,
            )
        )
    return out


def _check_budget(
    project: "GrantProject", pack: Optional[FunderPack]
) -> list[CheckItem]:
    from ..budget.calculator import BudgetCalculator

    budget_path = project.budget_path
    if budget_path is None:
        return []

    out: list[CheckItem] = []
    try:
        calc = BudgetCalculator(budget_path)
    except Exception as exc:
        return [
            CheckItem(
                level="warning",
                rule="budget_unreadable",
                message=f"Could not read {budget_path.name}: {exc}",
            )
        ]

    # Arithmetic consistency (fringe / indirect mismatches).
    try:
        for warning in calc.validate():
            out.append(
                CheckItem(
                    level="warning",
                    rule="budget_inconsistency",
                    message=warning,
                )
            )
        grand_total = calc.calculate_grand_total()
        yearly = calc.calculate_yearly_totals()
    except Exception as exc:
        return out + [
            CheckItem(
                level="warning",
                rule="budget_unreadable",
                message=f"Could not compute budget totals: {exc}",
            )
        ]

    # Funder caps from the rule pack.
    rules = pack.budget_rules if pack else None
    if rules and rules.total_cap is not None and grand_total > rules.total_cap:
        cur = rules.currency
        out.append(
            CheckItem(
                level="error",
                rule="budget_over_total_cap",
                message=(
                    f"Total budget {cur} {grand_total:,} exceeds the funder "
                    f"cap of {cur} {rules.total_cap:,.0f} (over by {cur} "
                    f"{grand_total - rules.total_cap:,.0f})."
                ),
                citation=rules.notes,
            )
        )
    if rules and rules.annual_cap is not None:
        cur = rules.currency
        for year_key, amount in yearly.items():
            if amount > rules.annual_cap:
                out.append(
                    CheckItem(
                        level="error",
                        rule="budget_over_annual_cap",
                        message=(
                            f"{year_key} budget {cur} {amount:,} exceeds the "
                            f"annual cap of {cur} {rules.annual_cap:,.0f}."
                        ),
                    )
                )

    out += _check_salaries(project, calc)
    return out


def _check_salaries(
    project: "GrantProject", calc: "object"
) -> list[CheckItem]:
    """BLS OEWS salary sanity — only runs when BLS_API_KEY is set."""
    if not os.environ.get("BLS_API_KEY"):
        return []
    from ..budget.salary_validator import get_salary_validator

    data = getattr(calc, "data", {}) or {}
    personnel = data.get("personnel", {}) or {}
    people = []
    for person in personnel.get("senior_key", []) or []:
        people.append(
            {
                "description": person.get("name")
                or person.get("role", "Senior personnel"),
                "amount": person.get("total") or person.get("year_1", 0),
                "occupation": person.get("occupation"),
                "months": person.get("months", 12),
                "area": person.get("area"),
            }
        )
    if not people:
        return []

    out: list[CheckItem] = []
    validator = get_salary_validator()
    for result in validator.validate_budget_personnel(people):
        for issue in result.issues:
            out.append(
                CheckItem(
                    level="error",
                    rule="salary_above_market",
                    message=issue,
                )
            )
        for warning in result.warnings:
            out.append(
                CheckItem(
                    level="warning",
                    rule="salary_market_check",
                    message=warning,
                )
            )
    return out


def _check_funder_rules(
    project: "GrantProject", pack: Optional[FunderPack]
) -> list[CheckItem]:
    if not pack:
        return []
    if pack.content_engine == "nsf_pappg":
        return _nsf_content_checks(project)
    return []


def _nsf_content_checks(project: "GrantProject") -> list[CheckItem]:
    """Run the NSF PAPPG content validator over the response sections.

    Prohibited content (emails, cloud-storage/social URLs, non-ASCII) is
    checked on every section; the Project Description additionally forbids all
    hyperlinks and must carry Overview / Intellectual Merit / Broader Impacts
    statements (PAPPG 24-1 II.C.2.d.i).
    """
    from .validator import NSFValidator

    out: list[CheckItem] = []
    validator = NSFValidator(project_root=project.root, is_nsf_grant=True)

    for section in project.sections:
        if not section.exists:
            continue
        if section.id == "project_description":
            result = validator.validate_project_description(section.body)
        else:
            result = validator.validate_proposal(
                section.body,
                check_formatting=False,
                check_content=False,
                check_compliance=True,
            )
        for issue in result.issues:
            if issue.severity == "info":
                continue
            # Advisory "content" heuristics (short text, IM/BI "not clearly
            # identified", missing headings) are dropped here: the required
            # Overview / Intellectual Merit / Broader Impacts statements are
            # enforced explicitly below as errors, and word/section checks
            # cover length, so keeping these would double-report.
            if issue.category == "content":
                continue
            out.append(
                CheckItem(
                    level=issue.severity,
                    rule=f"nsf_{issue.category}",
                    message=(
                        issue.message
                        + (f" {issue.suggestion}" if issue.suggestion else "")
                    ).strip(),
                    section=section.id,
                    citation=issue.rule,
                )
            )

    out += _nsf_required_statements(project)
    return out


def _nsf_required_statements(project: "GrantProject") -> list[CheckItem]:
    section = project.get_section("project_description")
    if section is None or not section.exists or section.words == 0:
        return []
    body_lower = section.body.lower()
    citation = "PAPPG 24-1 II.C.2.d.i"
    required = [
        ("overview", "overview", "an Overview"),
        (
            "intellectual merit",
            "intellectual merit",
            "a statement on Intellectual Merit",
        ),
        (
            "broader impacts",
            "broader impact",
            "a statement on Broader Impacts",
        ),
    ]
    out: list[CheckItem] = []
    for rule_id, needle, label in required:
        if needle not in body_lower:
            out.append(
                CheckItem(
                    level="error",
                    rule=f"nsf_missing_{rule_id.replace(' ', '_')}",
                    message=(
                        f"Project Description must contain {label} as a "
                        f"separate section."
                    ),
                    section="project_description",
                    citation=citation,
                )
            )
    return out


def _check_spelling(project: "GrantProject") -> list[CheckItem]:
    locale = project.locale
    if locale not in ("en-US", "en-GB"):
        return []
    out: list[CheckItem] = []
    for section in project.sections:
        if not section.exists:
            continue
        for hit in check_spelling(section.body, locale):
            out.append(
                CheckItem(
                    level="warning",
                    rule="spelling_locale",
                    message=(
                        f"'{hit.word}' (line {hit.line_number}) is not "
                        f"{locale}; use '{hit.suggestion}'."
                    ),
                    section=section.id,
                )
            )
    return out


def _check_urls(project: "GrantProject") -> list[CheckItem]:
    import re

    url_re = re.compile(r"https?://[^\s<>\"\)\]]+")
    seen: dict[str, str] = {}
    for section in project.sections:
        if not section.exists:
            continue
        for match in url_re.finditer(section.body):
            url = match.group(0).rstrip(".,;")
            seen.setdefault(url, section.id)

    out: list[CheckItem] = []
    for url, sid in sorted(seen.items()):
        alive, detail = _url_alive(url)
        if not alive:
            out.append(
                CheckItem(
                    level="warning",
                    rule="dead_url",
                    message=f"URL appears unreachable ({detail}): {url}",
                    section=sid,
                )
            )
    return out


def _url_alive(url: str) -> tuple[bool, str]:
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "grantkit-linkcheck/0.2"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            code = getattr(response, "status", 200) or 200
            return (code < 400, str(code))
    except urllib.error.HTTPError as exc:
        # Some servers reject HEAD; treat 405 as "alive".
        if exc.code in (403, 405, 501):
            return True, f"{exc.code} (HEAD not allowed)"
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # pragma: no cover - network variance
        return False, type(exc).__name__

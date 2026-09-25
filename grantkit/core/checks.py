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
* **budget** — arithmetic consistency (fringe/indirect), funder caps,
  pack-declared preparation evidence, and — only when ``BLS_API_KEY`` /
  ``GSA_API_KEY`` are set — BLS salary and GSA per-diem sanity (these make
  network calls, so they are opt-in).
* **selection model** — when grant.yaml binds a ``budget_model:`` portfolio
  selection, the portfolio integrity gates run (schema validation,
  referential checks, the co-funding gate) plus funder caps against the
  compiled selection total.
* **funder rules** — machine-checkable content rules selected by the pack.
  Packs also carry sourced formatting guidance; builders and PDF validation
  enforce or report only the subset they can establish.
* **spelling** — US/UK spelling locale from the pack.
* **urls** — link liveness. Network, so only when ``check_urls=True``
  (``grantkit check --urls``).
"""

from __future__ import annotations

import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import markdown as _markdown

from ..packs import BudgetPreparationRules, FunderPack
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
    items += _check_pack_section_contract(project, pack)
    items += _check_limits(project, pack)
    items += _check_placeholders(project)
    items += _check_markdown(project)
    items += _check_citations(project)
    items += _check_budget(project, pack)
    items += _check_selection_model(project)
    items += _check_proposal_rules(project, pack)
    items += _check_attachment_groups(project, pack)
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


def _check_pack_section_contract(
    project: "GrantProject", pack: Optional[FunderPack]
) -> list[CheckItem]:
    """Prevent grant.yaml from weakening or omitting pack requirements."""
    # Existing packs predate this hard contract and some intentionally permit
    # projects to select only a subset of their scaffold sections. Keep this
    # submission-readiness gate scoped to the PESOSE pack that declares it.
    if not pack or pack.id != "nsf-pesose-26-506-track-2":
        return []

    out: list[CheckItem] = []
    declared = {section.id: section for section in project.sections}
    for expected in pack.sections:
        section = declared.get(expected.id)
        if section is None:
            if expected.required:
                out.append(
                    CheckItem(
                        level="error",
                        rule="pack_required_section_missing",
                        message=(
                            f"The '{pack.id}' pack requires section "
                            f"'{expected.title}', but grant.yaml omits it."
                        ),
                        section=expected.id,
                        citation=pack.source_url,
                    )
                )
            continue

        if expected.required and not section.required:
            out.append(
                CheckItem(
                    level="error",
                    rule="pack_section_required_weakened",
                    message=(
                        f"The '{pack.id}' pack requires '{expected.title}', "
                        "but grant.yaml marks it optional."
                    ),
                    section=expected.id,
                    citation=pack.source_url,
                )
            )

        for attr, label in (
            ("word_limit", "word"),
            ("char_limit", "character"),
            ("page_limit", "page"),
        ):
            required_limit = getattr(expected, attr)
            declared_limit = getattr(section, attr)
            if required_limit is not None and (
                declared_limit is None
                or declared_limit <= 0
                or declared_limit > required_limit
            ):
                shown = (
                    "no limit" if declared_limit is None else declared_limit
                )
                out.append(
                    CheckItem(
                        level="error",
                        rule="pack_section_limit_weakened",
                        message=(
                            f"grant.yaml declares {shown} for "
                            f"'{expected.title}', but the '{pack.id}' pack "
                            f"sets a {required_limit}-{label} limit."
                        ),
                        section=expected.id,
                        citation=pack.source_url,
                    )
                )

        if section.format != expected.format:
            out.append(
                CheckItem(
                    level="error",
                    rule="pack_section_format_mismatch",
                    message=(
                        f"'{expected.title}' must use format "
                        f"'{expected.format}' under the '{pack.id}' pack; "
                        f"grant.yaml declares '{section.format}'."
                    ),
                    section=expected.id,
                    citation=pack.source_url,
                )
            )
    return out


def _check_limits(
    project: "GrantProject", pack: Optional[FunderPack]
) -> list[CheckItem]:
    out: list[CheckItem] = []
    pack_sections = (
        {section.id: section for section in pack.sections} if pack else {}
    )
    for section in project.sections:
        expected = pack_sections.get(section.id)
        word_limit = _strictest_limit(
            section.word_limit, expected.word_limit if expected else None
        )
        char_limit = _strictest_limit(
            section.char_limit, expected.char_limit if expected else None
        )
        page_limit = _strictest_limit(
            section.page_limit, expected.page_limit if expected else None
        )

        if word_limit is not None and section.words > word_limit:
            out.append(
                CheckItem(
                    level="error",
                    rule="word_limit_exceeded",
                    message=(
                        f"{section.words} words exceeds the "
                        f"{word_limit}-word limit for "
                        f"'{section.title}'."
                    ),
                    section=section.id,
                )
            )
        if char_limit is not None and section.chars > char_limit:
            out.append(
                CheckItem(
                    level="error",
                    rule="char_limit_exceeded",
                    message=(
                        f"{section.chars} characters exceeds the "
                        f"{char_limit}-character limit for "
                        f"'{section.title}'."
                    ),
                    section=section.id,
                )
            )
        if page_limit is not None and section.pages > page_limit:
            out.append(
                CheckItem(
                    level="warning",
                    rule="page_limit_estimate_exceeded",
                    message=(
                        f"~{section.pages:.1f} pages likely exceeds the "
                        f"{page_limit}-page limit for "
                        f"'{section.title}' (rough estimate at "
                        f"{project.words_per_page} words/page; confirm in the "
                        f"built PDF)."
                    ),
                    section=section.id,
                )
            )
    return out


def _strictest_limit(
    declared: Optional[int], packed: Optional[int]
) -> Optional[int]:
    limits = [
        value
        for value in (declared, packed)
        if value is not None and value > 0
    ]
    return min(limits) if limits else None


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

    # 2. Plain-text portals. Constructs `grantkit build` converts cleanly
    # (headers, emphasis, links, inline code, lists) are warnings — paste
    # from the built copy blocks, not the source file. Constructs that
    # survive conversion (tables, HTML comments) are errors. `fields`
    # sections hold individual form values, not pasted prose, so they are
    # not linted here.
    if not project.accepts_markdown:
        citation = _plain_text_citation(project.pack)
        validator = MarkdownContentValidator(accepts_markdown=False)
        for section in project.sections:
            if not section.exists or section.format == "fields":
                continue
            result = validator.validate_content(section.body, section.id)
            for violation in result.violations:
                converts = violation.syntax_type not in ("table", "comment")
                out.append(
                    CheckItem(
                        level="warning" if converts else "error",
                        rule="markdown_in_plain_text",
                        message=(
                            f"{violation.message} on line "
                            f"{violation.line_number} — "
                            + (
                                "stripped cleanly in the built copy blocks; "
                                "paste from the build output, not this file."
                                if converts
                                else "this does not convert to plain text "
                                "and would be pasted literally."
                            )
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
            return str(rule.citation) if rule.citation is not None else None
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
    if project.pack and project.pack.id.startswith("nsf-"):
        for key in sorted(set(used) & known):
            for issue in manager.validate_entries({key}):
                out.append(
                    CheckItem(
                        level="error",
                        rule="incomplete_bibliography_entry",
                        message=issue,
                        section=used[key],
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

    rules = pack.budget_rules if pack else None
    preparation = rules.preparation if rules else None
    budget_path = project.budget_path
    if budget_path is None:
        if preparation:
            return [
                CheckItem(
                    level="error",
                    rule="pesose_budget_preparation_unchecked",
                    message=(
                        "No budget.yaml is available, so the mandatory PESOSE "
                        "budget-preparation evidence requires manual review."
                    ),
                    section="budget_justification",
                    citation=preparation.citation or preparation.url,
                )
            ]
        return []

    out: list[CheckItem] = []
    try:
        calc = BudgetCalculator(budget_path)
    except Exception as exc:
        return [
            CheckItem(
                level="error" if preparation else "warning",
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
    except Exception:
        if preparation:
            out += _check_budget_preparation(
                project,
                preparation,
                getattr(calc, "data", {}) or {},
                grand_total=None,
            )
        return out + [
            CheckItem(
                level="error" if preparation else "warning",
                rule="budget_schema_mismatch",
                message=(
                    f"{budget_path.name} does not match grantkit's budget "
                    "schema (see docs), so arithmetic and cap checks were "
                    "skipped. Verify totals another way, or omit the file "
                    "from grantkit's view by renaming it."
                ),
            )
        ]

    # Funder caps from the rule pack.
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
    if preparation:
        out += _check_budget_preparation(
            project,
            preparation,
            getattr(calc, "data", {}) or {},
            grand_total=grand_total,
        )
    return out


def _check_budget_preparation(
    project: "GrantProject",
    rules: BudgetPreparationRules,
    data: dict,
    *,
    grand_total: Optional[float],
) -> list[CheckItem]:
    from ..budget.preparation import validate_budget_preparation

    section = project.get_section("budget_justification")
    body = section.body if section is not None and section.exists else ""
    citation = getattr(rules, "citation", None) or getattr(rules, "url", None)
    pesose = project.config.get("pesose", {})
    if not isinstance(pesose, dict):
        pesose = {}
    icorps_required = (
        "icorps_waiver_dates" in pesose
        and pesose.get("icorps_waiver_dates") is None
    )
    out = [
        CheckItem(
            level=finding.level,
            rule=finding.rule,
            message=finding.message,
            section="budget_justification",
            citation=citation,
        )
        for finding in validate_budget_preparation(
            data,
            rules,
            project_root=project.root,
            grand_total=grand_total,
            budget_justification=body,
            icorps_required=icorps_required,
            declared_icorps_budget_amount=pesose.get("icorps_budget_amount"),
        )
    ]

    compliance = _dict_or_none(pesose.get("compliance")) or {}
    eligibility = _dict_or_none(compliance.get("eligibility")) or {}
    from ..funders.nsf.pesose_compliance import (
        PESOSE_RULE_SOURCES,
        canonical_organization_type,
        validate_budget_scope_declarations,
    )

    eligibility_type = canonical_organization_type(
        eligibility.get("organization_type")
    )
    budget_type = canonical_organization_type(data.get("organization_type"))
    if (
        eligibility_type is not None
        and budget_type is not None
        and eligibility_type != budget_type
    ):
        out.append(
            CheckItem(
                level="error",
                rule="pesose_budget_organization_type_mismatch",
                message=(
                    "budget.yaml organization_type resolves to "
                    f"'{budget_type}', but "
                    "pesose.compliance.eligibility.organization_type "
                    f"resolves to '{eligibility_type}'. Use the same "
                    "proposing-organization type in both files so the "
                    "correct PESOSE salary route is applied."
                ),
                section="budget_justification",
                citation=citation,
            )
        )
    out += [
        CheckItem(
            level=finding.level,
            rule=finding.rule,
            message=finding.message,
            section="budget_justification",
            citation=PESOSE_RULE_SOURCES["eligibility"],
        )
        for finding in validate_budget_scope_declarations(eligibility, data)
    ]
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


def _check_selection_model(project: "GrantProject") -> list[CheckItem]:
    """Selection-model integrity — only when grant.yaml binds one.

    A ``budget_model:`` block binds the grant to one selection of a
    portfolio directory (see ``docs/budget-model.md``). This runs the
    portfolio integrity gates — schema validation, referential checks,
    the co-funding gate — plus the bound pack's funder caps against the
    compiled selection total.
    """
    binding = project.budget_model
    if not project.has_budget_model:
        return []
    if binding is None:
        return [
            CheckItem(
                level="error",
                rule="budget_model_invalid",
                message="budget_model must be a mapping.",
            )
        ]
    from ..menu.gates import run_gates
    from ..menu.loader import PortfolioError, load_portfolio

    portfolio_rel = binding.get("portfolio")
    if not portfolio_rel or not isinstance(portfolio_rel, str):
        return [
            CheckItem(
                level="error",
                rule="budget_model_invalid",
                message=(
                    "budget_model must carry a 'portfolio' path (a "
                    "directory with menu.yaml, rates.yaml, and "
                    "selections)."
                ),
            )
        ]
    try:
        portfolio_path = (project.root / portfolio_rel).resolve()
        portfolio = load_portfolio(portfolio_path)
    except (OSError, PortfolioError, RuntimeError, ValueError) as exc:
        return [
            CheckItem(
                level="error",
                rule="budget_model_unreadable",
                message=f"Could not load the bound portfolio: {exc}",
            )
        ]

    selection_id = binding.get("selection")
    if selection_id is not None and not isinstance(selection_id, str):
        return [
            CheckItem(
                level="error",
                rule="budget_model_invalid",
                message="budget_model.selection must be a string id.",
            )
        ]
    if selection_id is None and len(portfolio.selections) == 1:
        selection_id = portfolio.selections[0].id
    if (
        not isinstance(selection_id, str)
        or portfolio.get_selection(selection_id) is None
    ):
        available = ", ".join(portfolio.selection_ids) or "(none)"
        if selection_id is None:
            message = (
                "budget_model names no selection, but the portfolio does "
                "not have exactly one; add 'selection: <id>' "
                f"(available: {available})."
            )
        else:
            message = (
                f"budget_model selection '{selection_id}' not found in "
                f"the portfolio (available: {available})."
            )
        return [
            CheckItem(
                level="error",
                rule="unknown_selection",
                message=message,
            )
        ]
    return run_gates(portfolio, selection_id, project.pack)


def _check_funder_rules(
    project: "GrantProject", pack: Optional[FunderPack]
) -> list[CheckItem]:
    if not pack:
        return []
    if pack.content_engine == "nsf_pappg":
        return _nsf_content_checks(project)
    if pack.content_engine == "nsf_pesose_26_506_track_2":
        return _nsf_content_checks(project) + _pesose_track_2_checks(project)
    return []


def _check_proposal_rules(
    project: "GrantProject", pack: Optional[FunderPack]
) -> list[CheckItem]:
    if not pack or not pack.proposal_rules:
        return []
    rules = pack.proposal_rules
    out: list[CheckItem] = []
    if rules.title_prefix:
        if not project.title.startswith(rules.title_prefix):
            out.append(
                CheckItem(
                    level="error",
                    rule="title_prefix",
                    message=(
                        f"Proposal title must start with "
                        f"'{rules.title_prefix}'."
                    ),
                    citation=rules.citation,
                )
            )
        elif not project.title.removeprefix(rules.title_prefix).strip():
            out.append(
                CheckItem(
                    level="error",
                    rule="title_missing_project_name",
                    message=(
                        "Proposal title has the required prefix but no "
                        "project title after it."
                    ),
                    citation=rules.citation,
                )
            )

    if rules.max_duration_months is not None:
        duration = _project_duration_months(project)
        if duration is None:
            out.append(
                CheckItem(
                    level=(
                        "error"
                        if pack.content_engine == "nsf_pesose_26_506_track_2"
                        else "warning"
                    ),
                    rule="duration_not_declared",
                    message=(
                        "Proposal duration is not declared in grant.yaml; "
                        f"cannot verify the {rules.max_duration_months}-month "
                        "limit."
                    ),
                    citation=rules.citation,
                )
            )
        elif not math.isfinite(duration) or duration <= 0:
            out.append(
                CheckItem(
                    level="error",
                    rule="duration_invalid",
                    message=(
                        "Proposal duration must be a finite number greater "
                        "than zero."
                    ),
                    citation=rules.citation,
                )
            )
        elif duration > rules.max_duration_months:
            out.append(
                CheckItem(
                    level="error",
                    rule="duration_limit_exceeded",
                    message=(
                        f"Proposal duration is {duration:g} months; the limit "
                        f"is {rules.max_duration_months} months."
                    ),
                    citation=rules.citation,
                )
            )
    return out


def _project_duration_months(project: "GrantProject") -> Optional[float]:
    blocks = [project.config]
    grant_block = project.config.get("grant")
    if isinstance(grant_block, dict):
        blocks.append(grant_block)
    research_gov = project.config.get("research_gov")
    if isinstance(research_gov, dict):
        blocks.append(research_gov)

    for block in blocks:
        for key in ("duration_months", "requested_duration_months"):
            value = block.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    for block in blocks:
        value = block.get("duration_years")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value) * 12
    return None


def _check_attachment_groups(
    project: "GrantProject", pack: Optional[FunderPack]
) -> list[CheckItem]:
    if not pack:
        return []
    out: list[CheckItem] = []
    for group in pack.attachment_groups:
        paths = sorted(
            path for path in project.root.glob(group.glob) if path.is_file()
        )
        count = len(paths)
        if count < group.min_count:
            out.append(
                CheckItem(
                    level="error",
                    rule="attachment_count_below_minimum",
                    message=(
                        f"'{group.title}' has {count} file(s); at least "
                        f"{group.min_count} are required (glob: {group.glob})."
                    ),
                    section=group.id,
                    citation=group.citation,
                )
            )
        if group.max_count is not None and count > group.max_count:
            out.append(
                CheckItem(
                    level="error",
                    rule="attachment_count_above_maximum",
                    message=(
                        f"'{group.title}' has {count} file(s); no more than "
                        f"{group.max_count} are allowed (glob: {group.glob})."
                    ),
                    section=group.id,
                    citation=group.citation,
                )
            )
        if group.page_limit_each is not None and paths:
            out += _check_attachment_page_limits(group, paths)
    return out


def _check_attachment_page_limits(group, paths) -> list[CheckItem]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return [
            CheckItem(
                level="error",
                rule="attachment_pages_unchecked",
                message=(
                    f"Could not verify the {group.page_limit_each}-page limit "
                    f"for '{group.title}'; install grantkit[pdf]."
                ),
                section=group.id,
                citation=group.citation,
            )
        ]

    out: list[CheckItem] = []
    for path in paths:
        try:
            pages = len(PdfReader(str(path)).pages)
        except Exception as exc:
            out.append(
                CheckItem(
                    level="error",
                    rule="attachment_pdf_unreadable",
                    message=f"Could not inspect {path.name}: {exc}",
                    section=group.id,
                    citation=group.citation,
                )
            )
            continue
        if pages < 1:
            out.append(
                CheckItem(
                    level="error",
                    rule="attachment_pdf_empty",
                    message=f"{path.name} contains no PDF pages.",
                    section=group.id,
                    citation=group.citation,
                )
            )
        elif pages > group.page_limit_each:
            out.append(
                CheckItem(
                    level="error",
                    rule="attachment_page_limit_exceeded",
                    message=(
                        f"{path.name} is {pages} pages; the limit is "
                        f"{group.page_limit_each}."
                    ),
                    section=group.id,
                    citation=group.citation,
                )
            )
    return out


def _nsf_content_checks(project: "GrantProject") -> list[CheckItem]:
    """Run the NSF PAPPG content validator over the response sections.

    The Project Description forbids URLs and must carry an exact Broader
    Impacts heading. The Project Summary carries the separate Overview,
    Intellectual Merit, and Broader Impacts statements. Other proposal
    sections may contain ordinary bibliographic URLs and are not subjected to
    an invented domain allowlist.
    """
    from .validator import NSFValidator

    out: list[CheckItem] = []
    validator = NSFValidator(project_root=project.root, is_nsf_grant=True)

    section = project.get_section("project_description")
    if section is not None and section.exists:
        result = validator.validate_project_description(section.body)
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
                    section="project_description",
                    citation=issue.rule,
                )
            )

    out += _nsf_required_statements(project)
    return out


def _nsf_required_statements(project: "GrantProject") -> list[CheckItem]:
    out: list[CheckItem] = []
    citation = "PAPPG 24-1 II.D.2.b and II.D.2.d(i)"

    summary = project.get_section("project_summary")
    if summary is not None and summary.exists and summary.words:
        headings = _normalized_markdown_headings(summary.body)
        for rule_id, label in (
            ("overview", "Overview"),
            ("intellectual_merit", "Intellectual Merit"),
            ("broader_impacts", "Broader Impacts"),
        ):
            if label.lower() not in headings:
                out.append(
                    CheckItem(
                        level="warning",
                        rule=f"nsf_summary_missing_{rule_id}",
                        message=(
                            f"Could not verify a distinct {label} statement "
                            "from an own-line label in the Project Summary; "
                            "review the component substantively."
                        ),
                        section="project_summary",
                        citation=citation,
                    )
                )

    description = project.get_section("project_description")
    if description is not None and description.exists and description.words:
        headings = _normalized_markdown_headings(description.body)
        if "broader impacts" not in headings:
            out.append(
                CheckItem(
                    level="error",
                    rule="nsf_description_missing_broader_impacts",
                    message=(
                        "Project Description must contain a section labeled "
                        "'Broader Impacts', with that label as a heading on "
                        "its own line."
                    ),
                    section="project_description",
                    citation=citation,
                )
            )
    return out


def _normalized_markdown_headings(body: str) -> set[str]:
    import re

    headings: set[str] = set()
    required_labels = {"overview", "intellectual merit", "broader impacts"}
    for line in body.splitlines():
        heading = line.strip()
        if heading.startswith("#"):
            heading = re.sub(r"^#{1,6}\s+", "", heading)
        heading = heading.strip().strip("*_`").strip()
        heading = re.sub(r"^\d+(?:\.\d+)*[.:-]?\s*", "", heading)
        heading = heading.removesuffix(":").strip().casefold()
        if heading in required_labels:
            headings.add(heading)
    return headings


def _pesose_track_2_checks(project: "GrantProject") -> list[CheckItem]:
    out = _pesose_keywords_check(project)
    out += _pesose_icorps_check(project)
    out += _pesose_public_product_check(project)
    out += _pesose_structural_compliance_checks(project)
    out += _pesose_cost_sharing_check(project)
    out += _pesose_budget_completeness_check(project)
    return out


def _pesose_structural_compliance_checks(
    project: "GrantProject",
) -> list[CheckItem]:
    """Adapt project files and declarations to the pure PESOSE validator."""
    from ..funders.nsf.pesose_compliance import (
        NOT_APPLICABLE,
        PESOSE_RULE_SOURCES,
        SENIOR_KEY_DOCUMENT_FIELDS,
        validate_pesose_compliance,
    )

    pesose = project.config.get("pesose")
    compliance = pesose.get("compliance") if isinstance(pesose, dict) else None
    if not isinstance(compliance, dict):
        return [
            CheckItem(
                level="error",
                rule="pesose_compliance_declarations_missing",
                message=(
                    "Add a pesose.compliance mapping to grant.yaml so "
                    "GrantKit can evaluate eligibility, letters, personnel, "
                    "DMSP, and conditional NSF documents."
                ),
                citation="NSF 26-506 and PAPPG 24-1",
            )
        ]

    letters = _dict_or_none(compliance.get("letters"))
    personnel = _dict_or_none(compliance.get("personnel"))
    senior_key = _dict_or_none(compliance.get("senior_key"))
    mentoring = _dict_or_none(compliance.get("mentoring_plan"))

    letter_manifest = (
        _dict_or_none(letters.get("manifest")) if letters else None
    )
    actual_letter_files = [
        path.relative_to(project.root).as_posix()
        for path in sorted(project.root.glob("letters/*.pdf"))
        if path.is_file()
    ]
    actual_letter_page_counts = _pdf_page_counts(project, actual_letter_files)

    senior_key_manifest = (
        _dict_or_none(senior_key.get("documents")) if senior_key else None
    )
    actual_senior_key_files, senior_key_file_findings = (
        _senior_key_document_evidence(
            project,
            senior_key_manifest,
            SENIOR_KEY_DOCUMENT_FIELDS,
        )
    )
    synergistic_files = _manifest_field_files(
        senior_key_manifest, "synergistic_activities_file"
    )
    actual_synergistic_page_counts = _pdf_page_counts(
        project, synergistic_files
    )

    personnel_section = project.get_section("personnel_collaborators")
    dmsp_section = project.get_section("data_management_and_sharing_plan")
    declared_submission_date = compliance.get("proposal_submission_date")
    submission_date_uses_deadline = not (
        isinstance(declared_submission_date, str)
        and declared_submission_date.strip()
    )
    proposal_submission_date = declared_submission_date
    if submission_date_uses_deadline:
        proposal_submission_date = project.deadline
    findings = validate_pesose_compliance(
        proposal_submission_date=proposal_submission_date,
        eligibility=_dict_or_none(compliance.get("eligibility")),
        letter_manifest=letter_manifest,
        actual_letter_files=actual_letter_files,
        actual_letter_page_counts=actual_letter_page_counts,
        facilities_continuation=(
            _dict_or_none(letters.get("facilities_continuation"))
            if letters
            else None
        ),
        personnel_markdown=(
            personnel_section.body if personnel_section is not None else None
        ),
        declared_roster=(
            personnel.get("declared_roster") if personnel else None
        ),
        personnel_declarations=personnel,
        senior_key_document_manifest=senior_key_manifest,
        declared_senior_key_people=(
            senior_key.get("declared_people") if senior_key else None
        ),
        actual_senior_key_document_files=actual_senior_key_files,
        actual_synergistic_activities_page_counts=(
            actual_synergistic_page_counts
        ),
        prior_nsf_support_declarations=_dict_or_none(
            compliance.get("prior_nsf_support")
        ),
        mentoring_plan_declarations=mentoring,
        mentoring_plan_evidence=_mentoring_plan_evidence(
            project, mentoring, NOT_APPLICABLE
        ),
        supplement_1_declarations=_dict_or_none(
            compliance.get("supplement_1")
        ),
        dmsp_markdown=dmsp_section.body if dmsp_section is not None else None,
        dmsp_declarations=_dict_or_none(compliance.get("dmsp")),
        manual_review_attestations=_dict_or_none(
            compliance.get("manual_review")
        ),
        award_condition_attestations=_dict_or_none(
            compliance.get("award_conditions")
        ),
    )

    out = senior_key_file_findings + [
        CheckItem(
            level=finding.level,
            rule=finding.rule,
            message=finding.message,
            section=_pesose_finding_section(finding.rule),
            citation=_pesose_finding_citation(
                finding.rule, PESOSE_RULE_SOURCES
            ),
        )
        for finding in findings
    ]
    if submission_date_uses_deadline:
        out.append(
            CheckItem(
                level="warning",
                rule="pesose_submission_date_uses_deadline",
                message=(
                    "pesose.compliance.proposal_submission_date is missing "
                    "or blank; "
                    "research-security training recency was checked against "
                    "the proposal deadline. Declare the planned submission "
                    "date if it will be earlier."
                ),
                citation="NSF Important Notice 149, section 2",
            )
        )
    if compliance.get("pappg_conditional_requirements_reviewed") is not True:
        out.append(
            CheckItem(
                level="warning",
                rule="pesose_pappg_conditional_requirements_manual_review",
                message=(
                    "An AOR must review conditional PAPPG requirements that "
                    "GrantKit does not infer: former-NSF substitute "
                    "negotiators; off-campus/off-site plans; human subjects; "
                    "vertebrate animals; DURC; historic places; and Tribal "
                    "impacts or approvals. Set "
                    "pesose.compliance.pappg_conditional_requirements_reviewed: "
                    "true after that review."
                ),
                citation="PAPPG 24-1 II.D.1.f, II.D.2.i, and II.E",
            )
        )
    return out


def _dict_or_none(value):
    return value if isinstance(value, dict) else None


def _senior_key_document_evidence(
    project: "GrantProject",
    manifest,
    file_fields,
) -> tuple[list[str], list[CheckItem]]:
    """Validate local Senior/Key artifacts before manifest reconciliation."""
    if not isinstance(manifest, dict):
        return [], []
    paths: set[str] = set()
    findings: list[CheckItem] = []
    pdf_fields = {
        "biographical_sketch_file",
        "current_and_pending_support_file",
        "synergistic_activities_file",
    }
    for person, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        for field_name in file_fields:
            value = entry.get(field_name)
            if not isinstance(value, str) or not value.strip():
                continue
            candidate = project.root / value
            try:
                resolved = candidate.resolve()
                relative = resolved.relative_to(project.root)
            except (OSError, ValueError):
                continue
            if not resolved.is_file():
                continue

            valid = False
            expected = ""
            if field_name in pdf_fields:
                expected = "a readable, nonempty PDF"
                if resolved.suffix.casefold() == ".pdf":
                    counts = _pdf_page_counts(project, [relative.as_posix()])
                    valid = counts.get(relative.as_posix(), 0) > 0
            elif field_name == "collaborators_and_other_affiliations_file":
                expected = "a valid NSF COA .xlsx workbook"
                valid = _is_readable_xlsx(resolved)

            if valid:
                paths.add(relative.as_posix())
            else:
                findings.append(
                    CheckItem(
                        level="error",
                        rule="pesose_senior_key_document_unreadable",
                        message=(
                            f"{person!s} {field_name} must be {expected}: "
                            f"{relative.as_posix()}."
                        ),
                        citation="PAPPG 24-1 II.D.2.h",
                    )
                )
    return sorted(paths), findings


def _is_readable_xlsx(path) -> bool:
    import zipfile
    from xml.etree import ElementTree

    if path.suffix.casefold() != ".xlsx" or not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {
                "[Content_Types].xml",
                "_rels/.rels",
                "xl/workbook.xml",
                "xl/_rels/workbook.xml.rels",
            }
            if not required <= names:
                return False

            content_types = ElementTree.fromstring(
                archive.read("[Content_Types].xml")
            )
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            workbook_relationships = ElementTree.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )

            workbook_content_type = (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet.main+xml"
            )
            has_workbook_content_type = any(
                node.attrib.get("PartName") == "/xl/workbook.xml"
                and node.attrib.get("ContentType") == workbook_content_type
                for node in content_types
            )
            if not has_workbook_content_type:
                return False

            relationship_by_id = {
                node.attrib.get("Id"): node.attrib.get("Target")
                for node in workbook_relationships
                if node.attrib.get("Type", "").endswith("/worksheet")
            }
            relationship_key = (
                "{http://schemas.openxmlformats.org/officeDocument/2006/"
                "relationships}id"
            )
            sheet_nodes = workbook.findall(
                ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/"
                "main}sheet"
            )
            if not sheet_nodes:
                return False

            for sheet in sheet_nodes:
                target = relationship_by_id.get(
                    sheet.attrib.get(relationship_key)
                )
                if not target:
                    return False
                worksheet_path = target.lstrip("/")
                if not worksheet_path.startswith("xl/"):
                    worksheet_path = f"xl/{worksheet_path}"
                if worksheet_path not in names:
                    return False
                ElementTree.fromstring(archive.read(worksheet_path))
            return True
    except (
        OSError,
        KeyError,
        ValueError,
        zipfile.BadZipFile,
        ElementTree.ParseError,
    ):
        return False


def _manifest_field_files(manifest, field: str) -> list[str]:
    if not isinstance(manifest, dict):
        return []
    return sorted(
        {
            value
            for entry in manifest.values()
            if isinstance(entry, dict)
            and isinstance((value := entry.get(field)), str)
            and value.strip()
        }
    )


def _pdf_page_counts(project: "GrantProject", paths) -> dict[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return {}

    counts: dict[str, int] = {}
    for value in paths:
        if not isinstance(value, str):
            continue
        candidate = project.root / value
        try:
            resolved = candidate.resolve()
            relative = resolved.relative_to(project.root).as_posix()
            counts[relative] = len(PdfReader(str(resolved)).pages)
        except Exception:
            continue
    return counts


def _mentoring_plan_evidence(project, declarations, not_applicable):
    """Build file/page evidence without treating an authoring stub as upload."""
    upload_file = (
        declarations.get("upload_file")
        if isinstance(declarations, dict)
        else None
    )
    if not isinstance(upload_file, str) or upload_file == not_applicable:
        return {"file_present": False, "page_count": not_applicable}

    candidate = project.root / upload_file
    try:
        resolved = candidate.resolve()
        resolved.relative_to(project.root)
    except (OSError, ValueError):
        return {"file_present": False, "page_count": not_applicable}
    if not resolved.is_file():
        return {"file_present": False, "page_count": not_applicable}

    try:
        from pypdf import PdfReader

        pages = len(PdfReader(str(resolved)).pages)
    except Exception:
        pages = None
    return {"file_present": True, "page_count": pages}


def _pesose_finding_section(rule: str) -> Optional[str]:
    if rule.startswith("pesose_letters_"):
        return "letters_of_collaboration"
    if rule.startswith("pesose_personnel_"):
        return "personnel_collaborators"
    if rule.startswith("pesose_dmsp_"):
        return "data_management_and_sharing_plan"
    if rule.startswith("pesose_mentoring_"):
        return "mentoring_plan"
    if rule.startswith("pesose_prior_nsf_") or rule.startswith(
        "pesose_manual_"
    ):
        return "project_description"
    return None


def _pesose_finding_citation(rule: str, sources: dict[str, str]) -> str:
    if rule.startswith("pesose_eligibility_"):
        return sources["eligibility"]
    if rule.startswith("pesose_letters_"):
        return sources["letters"]
    if rule.startswith("pesose_personnel_"):
        return sources["personnel"]
    if rule.startswith("pesose_senior_key_"):
        return sources["senior_key_documents"]
    if rule.startswith("pesose_prior_nsf_"):
        return sources["prior_nsf_support"]
    if rule.startswith("pesose_mentoring_"):
        return sources["mentoring_plan"]
    if rule.startswith("pesose_supplement_1_"):
        return sources["supplement_1"]
    if rule == "pesose_proposal_submission_date":
        return sources["supplement_1"]
    if rule.startswith("pesose_dmsp_"):
        return sources["dmsp"]
    if rule.startswith("pesose_manual_track2_"):
        return sources["track_2_activities"]
    if rule.startswith("pesose_award_condition_"):
        return sources["award_conditions"]
    return sources["proposal_content"]


def _pesose_keywords_check(project: "GrantProject") -> list[CheckItem]:
    section = project.get_section("project_summary")
    if section is None or not section.exists or not section.body.strip():
        return []
    citation = "NSF 26-506 V.A, Project Summary"
    last_line = next(
        line.strip()
        for line in reversed(section.body.splitlines())
        if line.strip()
    )
    has_recommended_label = last_line.startswith("Keywords:")
    keyword_text = (
        last_line.removeprefix("Keywords:")
        if has_recommended_label
        else last_line
    )
    out: list[CheckItem] = []
    if not has_recommended_label:
        out.append(
            CheckItem(
                level="warning",
                rule="pesose_summary_keywords_last_line",
                message=(
                    "NSF says the final prioritized keyword list should "
                    "start with 'Keywords:'."
                ),
                section="project_summary",
                citation=citation,
            )
        )
    keywords = [item.strip() for item in keyword_text.split(";")]
    if not 2 <= len(keywords) <= 5 or any(not item for item in keywords):
        out.append(
            CheckItem(
                level="error",
                rule="pesose_summary_keyword_count",
                message=(
                    "Project Summary must end with 2-5 nonempty, "
                    "semicolon-separated keywords or phrases."
                ),
                section="project_summary",
                citation=citation,
            )
        )
    return out


def _pesose_icorps_check(project: "GrantProject") -> list[CheckItem]:
    pesose = project.config.get("pesose", {})
    if not isinstance(pesose, dict):
        pesose = {}
    declared = "icorps_waiver_dates" in pesose
    dates = pesose.get("icorps_waiver_dates")
    if not declared:
        return [
            CheckItem(
                level="error",
                rule="pesose_icorps_status_undeclared",
                message=(
                    "Declare pesose.icorps_waiver_dates in grant.yaml, or "
                    "set it to null when the proposal budgets the required "
                    "experiential activity."
                ),
                citation="NSF 26-506 V.A, Experiential Activities",
            )
        ]
    if dates is None:
        amount = pesose.get("icorps_budget_amount")
        if amount is None:
            return [
                CheckItem(
                    level="error",
                    rule="pesose_icorps_budget_undeclared",
                    message=(
                        "No prior I-Corps waiver dates are declared. Add "
                        "pesose.icorps_budget_amount so GrantKit can verify "
                        "the required experiential-activity budget."
                    ),
                    citation="NSF 26-506 V.A, Experiential Activities",
                )
            ]
        if (
            not isinstance(amount, (int, float))
            or isinstance(amount, bool)
            or not math.isfinite(amount)
            or amount < 0
        ):
            return [
                CheckItem(
                    level="error",
                    rule="pesose_icorps_budget_invalid",
                    message=(
                        "pesose.icorps_budget_amount must be a finite, "
                        "non-negative number when no waiver is claimed."
                    ),
                    citation="PESOSE budget-preparation guidance",
                )
            ]
        if amount == 0:
            return [
                CheckItem(
                    level="warning",
                    rule="pesose_icorps_budget_zero_manual_review",
                    message=(
                        "The non-waived I-Corps budget is zero. NSF permits "
                        "up to USD 30,000 rather than setting a positive "
                        "minimum; confirm that required participation can be "
                        "completed without requested costs."
                    ),
                    citation="PESOSE budget-preparation guidance",
                )
            ]
        if amount > 30000:
            return [
                CheckItem(
                    level="error",
                    rule="pesose_icorps_budget_over_cap",
                    message=(
                        f"I-Corps budget is USD {amount:,.0f}; PESOSE permits "
                        "no more than USD 30,000."
                    ),
                    citation="PESOSE budget-preparation guidance",
                )
            ]
        return []
    if not isinstance(dates, str) or not dates.strip():
        return [
            CheckItem(
                level="error",
                rule="pesose_icorps_dates_invalid",
                message="pesose.icorps_waiver_dates must be text or null.",
                citation="NSF 26-506 V.A, Experiential Activities",
            )
        ]
    out: list[CheckItem] = []
    award = pesose.get("icorps_track1_award")
    if not isinstance(award, (str, int)) or not str(award).strip():
        out.append(
            CheckItem(
                level="warning",
                rule="pesose_icorps_track1_award_missing",
                message=(
                    "Record the prior Track 1 award under which I-Corps for "
                    "PESOSE was completed as internal waiver evidence. The "
                    "solicitation requires successful completion, dates, and "
                    "outcomes, but does not expressly require the award "
                    "number in the proposal."
                ),
                citation="NSF 26-506 V.A, Experiential Activities",
            )
        )
    if pesose.get("icorps_waiver_successfully_completed") is not True:
        out.append(
            CheckItem(
                level="error",
                rule="pesose_icorps_waiver_completion_unconfirmed",
                message=(
                    "Set pesose.icorps_waiver_successfully_completed: true "
                    "only after confirming successful completion under the "
                    "identified Track 1 award."
                ),
                citation="NSF 26-506 V.A, Experiential Activities",
            )
        )

    section = project.get_section("project_description")
    if section is None or not section.exists or not section.body.strip():
        return out
    first_line = next(
        line.strip() for line in section.body.splitlines() if line.strip()
    )
    if dates not in first_line:
        out.append(
            CheckItem(
                level="error",
                rule="pesose_icorps_dates_first_line",
                message=(
                    "The configured I-Corps waiver dates must appear on the "
                    "first nonblank line of the Project Description."
                ),
                section="project_description",
                citation="NSF 26-506 V.A, Experiential Activities",
            )
        )
    if pesose.get("icorps_outcomes_described") is not True:
        out.append(
            CheckItem(
                level="error",
                rule="pesose_icorps_outcomes_unreviewed",
                message=(
                    "Confirm by setting pesose.icorps_outcomes_described: "
                    "true only after substantive review establishes that the "
                    "Project Description explains the I-Corps outcomes."
                ),
                section="project_description",
                citation="NSF 26-506 V.A, Experiential Activities",
            )
        )
    return out


def _pesose_public_product_check(project: "GrantProject") -> list[CheckItem]:
    """Verify the solicitation's citation pointer to the existing product."""
    pesose = project.config.get("pesose", {})
    if not isinstance(pesose, dict):
        pesose = {}
    key = pesose.get("public_product_citation_key")
    citation = "NSF 26-506 V.A, Project Description item 1"
    if key is None:
        return [
            CheckItem(
                level="error",
                rule="pesose_public_product_citation_undeclared",
                message=(
                    "Declare pesose.public_product_citation_key in grant.yaml "
                    "so GrantKit can verify the required pointer to the "
                    "existing public open-source product."
                ),
                citation=citation,
            )
        ]
    if not isinstance(key, str) or not key.strip():
        return [
            CheckItem(
                level="error",
                rule="pesose_public_product_citation_invalid",
                message=(
                    "pesose.public_product_citation_key must be a non-empty "
                    "BibTeX citation key."
                ),
                citation=citation,
            )
        ]

    out: list[CheckItem] = []
    if pesose.get("public_product_open_source") is not True:
        out.append(
            CheckItem(
                level="error",
                rule="pesose_public_product_open_source_unconfirmed",
                message=(
                    "Set pesose.public_product_open_source: true only after "
                    "confirming that the cited product is publicly available "
                    "and modifiable as required by PESOSE."
                ),
                citation=citation,
            )
        )
    license_id = pesose.get("public_product_license")
    if not isinstance(license_id, str) or not license_id.strip():
        out.append(
            CheckItem(
                level="error",
                rule="pesose_public_product_license_missing",
                message=(
                    "Declare pesose.public_product_license with the existing "
                    "product's open-source license identifier."
                ),
                citation=citation,
            )
        )
    description = project.get_section("project_description")
    if description is not None and description.exists:
        from ..references.citation_extractor import CitationExtractor

        used = {
            match.citation_key
            for match in CitationExtractor().extract_citations_from_text(
                description.body
            )
        }
        if key not in used:
            out.append(
                CheckItem(
                    level="error",
                    rule="pesose_public_product_not_cited",
                    message=(
                        f"Project Description must cite the configured public "
                        f"product entry '[@{key}]'."
                    ),
                    section="project_description",
                    citation=citation,
                )
            )

    bib_path = project.references_path
    if bib_path is None:
        out.append(
            CheckItem(
                level="error",
                rule="pesose_public_product_reference_missing",
                message=(
                    "The required public-product citation cannot be verified "
                    "because references.bib is missing."
                ),
                citation=citation,
            )
        )
        return out

    from ..references.bibtex_manager import BibTeXManager

    manager = BibTeXManager(project.root)
    manager.load_bibliography(bib_path)
    entry = manager.get_entry(key)
    if entry is None:
        out.append(
            CheckItem(
                level="error",
                rule="pesose_public_product_reference_missing",
                message=(
                    f"Configured public-product entry '{key}' is missing "
                    f"from {bib_path.name}."
                ),
                citation=citation,
            )
        )
    elif not entry.url and not entry.doi:
        out.append(
            CheckItem(
                level="error",
                rule="pesose_public_product_reference_url_missing",
                message=(
                    f"Public-product reference '{key}' must contain a public "
                    "URL or DOI that resolves to the product."
                ),
                citation=citation,
            )
        )
    elif not any(
        target is not None and _is_public_http_url(target)
        for target in (entry.url, _doi_url(entry.doi))
    ):
        out.append(
            CheckItem(
                level="error",
                rule="pesose_public_product_reference_url_invalid",
                message=(
                    f"Public-product reference '{key}' must contain a valid "
                    "public HTTP(S) URL in its url field or a bare DOI "
                    "identifier (beginning '10.') in its doi field, not a "
                    "local, private, or malformed address."
                ),
                citation=citation,
            )
        )
    return out


def _doi_url(value: Optional[str]) -> Optional[str]:
    """Return a resolver URL for a bare DOI stored in a BibTeX ``doi`` field."""
    import re

    if not isinstance(value, str):
        return None
    doi = value.strip()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi, flags=re.IGNORECASE):
        return None
    return f"https://doi.org/{doi}"


def _is_public_http_url(value: str) -> bool:
    """Return whether ``value`` is an absolute, non-private HTTP(S) URL."""
    import ipaddress
    from urllib.parse import urlparse

    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        hostname = parsed.hostname.casefold().rstrip(".")
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return False
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return "." in hostname
        return not (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        )
    except (TypeError, ValueError):
        return False


def _pesose_cost_sharing_check(project: "GrantProject") -> list[CheckItem]:
    """Reject explicit voluntary committed cost sharing declarations."""
    values = []
    for block in (project.config, project.config.get("grant", {})):
        if (
            isinstance(block, dict)
            and "voluntary_committed_cost_sharing" in block
        ):
            values.append(block["voluntary_committed_cost_sharing"])

    if project.budget_path is not None:
        try:
            import yaml

            budget = yaml.safe_load(
                project.budget_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, yaml.YAMLError):
            budget = None
        if isinstance(budget, dict):
            for key in (
                "voluntary_committed_cost_sharing",
                "voluntary_cost_sharing",
            ):
                if key in budget:
                    values.append(budget[key])

    if any(_is_positive_commitment(value) for value in values):
        return [
            CheckItem(
                level="error",
                rule="pesose_voluntary_cost_sharing_prohibited",
                message=(
                    "PESOSE prohibits voluntary committed cost sharing; "
                    "remove the declared commitment."
                ),
                citation="NSF 26-506 V.B, Cost Sharing",
            )
        ]
    return []


def _pesose_budget_completeness_check(
    project: "GrantProject",
) -> list[CheckItem]:
    """Reject an absent or zero-dollar working shell as submission-ready."""
    if project.budget_path is None:
        return [
            CheckItem(
                level="error",
                rule="pesose_budget_missing",
                message=(
                    "PESOSE Track 2 requires a proposal budget; bind a "
                    "completed budget.yaml before treating the proposal as "
                    "submission-ready."
                ),
                section="budget_justification",
                citation="NSF 26-506 V.A, Budget and Budget Justification",
            )
        ]
    try:
        from ..budget.calculator import BudgetCalculator

        total = BudgetCalculator(project.budget_path).calculate_grand_total()
    except Exception:
        return []  # _check_budget reports the unreadable/schema finding.
    if total <= 0:
        return [
            CheckItem(
                level="error",
                rule="pesose_budget_not_finalized",
                message=(
                    "The PESOSE budget totals zero; replace the working shell "
                    "with the completed Research.gov budget evidence before "
                    "submission."
                ),
                section="budget_justification",
                citation="NSF 26-506 V.A, Budget and Budget Justification",
            )
        ]
    return []


def _is_positive_commitment(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().casefold() not in {"", "0", "false", "no", "none"}
    if isinstance(value, dict):
        return any(_is_positive_commitment(item) for item in value.values())
    if isinstance(value, list):
        return any(_is_positive_commitment(item) for item in value)
    return False


def _check_spelling(project: "GrantProject") -> list[CheckItem]:
    locale = project.locale
    if locale not in ("en-US", "en-GB"):
        return []
    out: list[CheckItem] = []
    for section in project.sections:
        # Bibliographic titles, organization names, and quoted source text
        # must preserve their official spelling rather than be localized.
        if not section.exists or section.id == "references":
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
    for url in _budget_bls_urls(project):
        seen.setdefault(url, "budget_justification")
    for url in _public_product_reference_urls(project):
        seen.setdefault(url, "references")

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


def _public_product_reference_urls(project: "GrantProject") -> list[str]:
    """Return the PESOSE public-product URL for optional liveness checks."""
    pesose = project.config.get("pesose", {})
    if not isinstance(pesose, dict):
        return []
    key = pesose.get("public_product_citation_key")
    if not isinstance(key, str) or not key or project.references_path is None:
        return []
    try:
        from ..references.bibtex_manager import BibTeXManager

        manager = BibTeXManager(project.root)
        manager.load_bibliography(project.references_path)
        entry = manager.get_entry(key)
    except Exception:
        return []
    if entry is None:
        return []
    targets = [entry.url, _doi_url(entry.doi)]
    return [target for target in targets if target]


def _budget_bls_urls(project: "GrantProject") -> list[str]:
    """Return explicit BLS evidence links from budget.yaml, if readable."""
    budget_path = project.budget_path
    if budget_path is None:
        return []
    try:
        import yaml

        data = yaml.safe_load(budget_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return []

    urls: list[str] = []

    def visit(value) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "bls_url" and isinstance(item, str):
                    urls.append(item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    return urls


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

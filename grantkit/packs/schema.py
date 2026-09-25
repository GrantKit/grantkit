"""Schema for funder rule packs.

A rule pack YAML is parsed into a :class:`FunderPack`. The :func:`validate_pack`
function checks a raw dict against the documented schema and returns a list of
human-readable error strings (empty list == valid). It is used both at load time
and by the rule-pack schema tests.

Schema (top-level keys)
-----------------------
``id`` (str, required)
    Stable pack identifier, matches the YAML filename stem (e.g. ``nsf-pappg``).
``name`` (str, required)
    Human funder name (e.g. ``National Science Foundation``).
``program`` (str, optional)
    Default program/solicitation the pack targets.
``version`` (str, optional)
    Version of the underlying funder guidance (e.g. PAPPG ``24-1``).
``source_url`` (str, optional)
    Canonical solicitation / policy URL.
``locale`` (str, ``en-US`` | ``en-GB``)
    Spelling locale enforced by ``grantkit check``.
``provenance`` (str, optional)
    Free-text note on how the pack values were sourced.
``content_engine`` (str, optional)
    Named programmatic content checker to run.
``extends`` (str, optional)
    Parent pack id. The effective pack inherits the parent, recursively merges
    mappings, and replaces parent lists or scalar values with child values.
``sections`` (list, optional)
    Section definitions used to scaffold a grant. Each carries
    ``id``/``title``/``word_limit``/``char_limit``/``page_limit``/``required``/
    ``description``/``file``/``stage``/``format`` (``prose`` | ``fields``;
    ``fields`` sections hold individual form values and are exempt from
    plain-text portal linting).
``formatting_rules`` (list, optional)
    Documented formatting rules. Each carries ``id``/``description``/``severity``/
    ``citation``/``url``/``quote``/``applies_to``.
``budget_rules`` (mapping, optional)
    ``total_cap``/``annual_cap``/``indirect_rate_max``/``mtdc_excludes``/
    ``currency``/``notes`` and an optional structured ``preparation`` contract.
``proposal_rules`` (mapping, optional)
    Proposal-level constraints such as ``title_prefix`` and
    ``max_duration_months``.
``attachment_groups`` (list, optional)
    File groups with count and per-file page limits.
``portal`` (mapping, optional)
    ``accepts_markdown``/``plain_text_boxes``/``url``/``notes``.
``review_rubric`` (list, optional)
    Assessment criteria used by ``grantkit review``. Each carries
    ``id``/``name``/``description``/``citation``/``url``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional, TypeGuard

VALID_SEVERITIES = {"error", "warning", "info"}
VALID_LOCALES = {"en-US", "en-GB"}
VALID_CONTENT_ENGINES = {
    None,
    "nsf_pappg",
    "nsf_pesose_26_506_track_2",
}
VALID_SECTION_FORMATS = {"prose", "fields"}


@dataclass
class PackSection:
    """A section definition contributed by a funder pack."""

    id: str
    title: str
    word_limit: Optional[int] = None
    char_limit: Optional[int] = None
    page_limit: Optional[int] = None
    required: bool = True
    description: Optional[str] = None
    file: Optional[str] = None
    stage: Optional[str] = None
    #: ``prose`` (default) is pasted as a portal text box; ``fields`` holds
    #: individual form values and is exempt from plain-text portal linting.
    format: str = "prose"


@dataclass
class FormattingRule:
    """A documented funder formatting rule with a citation."""

    id: str
    description: str
    severity: str = "error"
    citation: Optional[str] = None
    url: Optional[str] = None
    quote: Optional[str] = None
    applies_to: str = "all"


@dataclass
class BudgetPreparationRules:
    """Source-backed budget-justification and attachment requirements."""

    max_budget_years: Optional[int] = None
    institutional_salary_org_types: list[str] = field(default_factory=list)
    bls_salary_org_types: list[str] = field(default_factory=list)
    bls_salary_percentile: Optional[float] = None
    lines_ab_employee_only: bool = False
    personnel_justification_fields_required: bool = False
    salary_months_justification_threshold: Optional[float] = None
    salary_hourly_month_hours: Optional[float] = None
    fringe_justification_fields: list[str] = field(default_factory=list)
    main_equipment_necessity_required: bool = False
    travel_breakdown_format: Optional[str] = None
    travel_cost_rules: dict[str, str] = field(default_factory=dict)
    materials_explanation_threshold_fraction: Optional[float] = None
    consultant_statement_threshold: Optional[float] = None
    consultant_justification_fields: list[str] = field(default_factory=list)
    equity_owner_payment_channels: list[str] = field(default_factory=list)
    subaward_detail_required: bool = False
    subaward_ip_rights_agreement_required: bool = False
    subaward_equipment_allowed: Optional[bool] = None
    line_g_services_description_required: bool = False
    de_minimis_indirect_rate: Optional[float] = None
    de_minimis_indirect_base: Optional[str] = None
    indirect_base_amount_verification_required: bool = False
    icorps_budget_cap: Optional[float] = None
    icorps_required_team_roles: list[str] = field(default_factory=list)
    icorps_allowed_cost_types: list[str] = field(default_factory=list)
    icorps_prohibited_cost_types: list[str] = field(default_factory=list)
    icorps_current_salary_cap_roles: list[str] = field(default_factory=list)
    icorps_domestic_travel_only: bool = False
    icorps_team_agreement_required: bool = False
    icorps_team_size_manual_review_max: Optional[int] = None
    icorps_training_format: Optional[str] = None
    icorps_context_url: Optional[str] = None
    citation: Optional[str] = None
    url: Optional[str] = None


@dataclass
class BudgetRules:
    """Funder budget constraints used by the budget checks."""

    total_cap: Optional[float] = None
    annual_cap: Optional[float] = None
    indirect_rate_max: Optional[float] = None
    mtdc_excludes: list[str] = field(default_factory=list)
    currency: str = "USD"
    notes: Optional[str] = None
    preparation: Optional[BudgetPreparationRules] = None


@dataclass
class ProposalRules:
    """Constraints that apply to the proposal as a whole."""

    title_prefix: Optional[str] = None
    max_duration_months: Optional[int] = None
    citation: Optional[str] = None


@dataclass
class AttachmentGroup:
    """A required or optional group of project attachments."""

    id: str
    title: str
    glob: str
    min_count: int = 0
    max_count: Optional[int] = None
    page_limit_each: Optional[int] = None
    citation: Optional[str] = None


@dataclass
class PortalQuirks:
    """Submission-portal quirks (e.g. plain-text-only boxes)."""

    accepts_markdown: bool = True
    plain_text_boxes: bool = False
    url: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class RubricCriterion:
    """A single assessment criterion for the review packet."""

    id: str
    name: str
    description: Optional[str] = None
    citation: Optional[str] = None
    url: Optional[str] = None


@dataclass
class FunderPack:
    """A fully-parsed funder rule pack."""

    id: str
    name: str
    program: Optional[str] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    extends: Optional[str] = None
    locale: str = "en-US"
    provenance: Optional[str] = None
    content_engine: Optional[str] = None
    sections: list[PackSection] = field(default_factory=list)
    formatting_rules: list[FormattingRule] = field(default_factory=list)
    budget_rules: Optional[BudgetRules] = None
    proposal_rules: Optional[ProposalRules] = None
    attachment_groups: list[AttachmentGroup] = field(default_factory=list)
    portal: PortalQuirks = field(default_factory=PortalQuirks)
    review_rubric: list[RubricCriterion] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def accepts_markdown(self) -> bool:
        """Whether the funder portal accepts markdown formatting."""
        return self.portal.accepts_markdown

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FunderPack":
        """Build a :class:`FunderPack` from a raw YAML dict.

        Assumes the dict has already passed :func:`validate_pack` (or is trusted).
        Unknown keys are ignored but preserved on ``raw``.
        """
        sections = [
            PackSection(
                id=s.get("id", ""),
                title=s.get("title", s.get("id", "")),
                word_limit=s.get("word_limit"),
                char_limit=s.get("char_limit"),
                page_limit=s.get("page_limit"),
                required=bool(s.get("required", True)),
                description=s.get("description"),
                file=s.get("file"),
                stage=s.get("stage"),
                format=(
                    s["format"]
                    if s.get("format") in VALID_SECTION_FORMATS
                    else "prose"
                ),
            )
            for s in data.get("sections", []) or []
        ]
        rules = [
            FormattingRule(
                id=r.get("id", ""),
                description=r.get("description", ""),
                severity=r.get("severity", "error"),
                citation=r.get("citation"),
                url=r.get("url"),
                quote=r.get("quote"),
                applies_to=r.get("applies_to", "all"),
            )
            for r in data.get("formatting_rules", []) or []
        ]
        budget_rules = None
        if data.get("budget_rules"):
            b = data["budget_rules"]
            preparation = None
            if b.get("preparation"):
                p = b["preparation"]
                preparation = BudgetPreparationRules(
                    max_budget_years=p.get("max_budget_years"),
                    institutional_salary_org_types=list(
                        p.get("institutional_salary_org_types", []) or []
                    ),
                    bls_salary_org_types=list(
                        p.get("bls_salary_org_types", []) or []
                    ),
                    bls_salary_percentile=p.get("bls_salary_percentile"),
                    lines_ab_employee_only=bool(
                        p.get("lines_ab_employee_only", False)
                    ),
                    personnel_justification_fields_required=bool(
                        p.get("personnel_justification_fields_required", False)
                    ),
                    salary_months_justification_threshold=p.get(
                        "salary_months_justification_threshold"
                    ),
                    salary_hourly_month_hours=p.get(
                        "salary_hourly_month_hours"
                    ),
                    fringe_justification_fields=list(
                        p.get("fringe_justification_fields", []) or []
                    ),
                    main_equipment_necessity_required=bool(
                        p.get("main_equipment_necessity_required", False)
                    ),
                    travel_breakdown_format=p.get("travel_breakdown_format"),
                    travel_cost_rules=dict(
                        p.get("travel_cost_rules", {}) or {}
                    ),
                    materials_explanation_threshold_fraction=p.get(
                        "materials_explanation_threshold_fraction"
                    ),
                    consultant_statement_threshold=p.get(
                        "consultant_statement_threshold"
                    ),
                    consultant_justification_fields=list(
                        p.get("consultant_justification_fields", []) or []
                    ),
                    equity_owner_payment_channels=list(
                        p.get("equity_owner_payment_channels", []) or []
                    ),
                    subaward_detail_required=bool(
                        p.get("subaward_detail_required", False)
                    ),
                    subaward_ip_rights_agreement_required=bool(
                        p.get("subaward_ip_rights_agreement_required", False)
                    ),
                    subaward_equipment_allowed=p.get(
                        "subaward_equipment_allowed"
                    ),
                    line_g_services_description_required=bool(
                        p.get("line_g_services_description_required", False)
                    ),
                    de_minimis_indirect_rate=p.get("de_minimis_indirect_rate"),
                    de_minimis_indirect_base=p.get("de_minimis_indirect_base"),
                    indirect_base_amount_verification_required=bool(
                        p.get(
                            "indirect_base_amount_verification_required", False
                        )
                    ),
                    icorps_budget_cap=p.get("icorps_budget_cap"),
                    icorps_required_team_roles=list(
                        p.get("icorps_required_team_roles", []) or []
                    ),
                    icorps_allowed_cost_types=list(
                        p.get("icorps_allowed_cost_types", []) or []
                    ),
                    icorps_prohibited_cost_types=list(
                        p.get("icorps_prohibited_cost_types", []) or []
                    ),
                    icorps_current_salary_cap_roles=list(
                        p.get("icorps_current_salary_cap_roles", []) or []
                    ),
                    icorps_domestic_travel_only=bool(
                        p.get("icorps_domestic_travel_only", False)
                    ),
                    icorps_team_agreement_required=bool(
                        p.get("icorps_team_agreement_required", False)
                    ),
                    icorps_team_size_manual_review_max=p.get(
                        "icorps_team_size_manual_review_max"
                    ),
                    icorps_training_format=p.get("icorps_training_format"),
                    icorps_context_url=p.get("icorps_context_url"),
                    citation=p.get("citation"),
                    url=p.get("url"),
                )
            budget_rules = BudgetRules(
                total_cap=b.get("total_cap"),
                annual_cap=b.get("annual_cap"),
                indirect_rate_max=b.get("indirect_rate_max"),
                mtdc_excludes=list(b.get("mtdc_excludes", []) or []),
                currency=b.get("currency", "USD"),
                notes=b.get("notes"),
                preparation=preparation,
            )
        proposal_rules = None
        if data.get("proposal_rules"):
            p = data["proposal_rules"]
            proposal_rules = ProposalRules(
                title_prefix=p.get("title_prefix"),
                max_duration_months=p.get("max_duration_months"),
                citation=p.get("citation"),
            )
        attachment_groups = [
            AttachmentGroup(
                id=a.get("id", ""),
                title=a.get("title", a.get("id", "")),
                glob=a.get("glob", ""),
                min_count=a.get("min_count", 0),
                max_count=a.get("max_count"),
                page_limit_each=a.get("page_limit_each"),
                citation=a.get("citation"),
            )
            for a in data.get("attachment_groups", []) or []
        ]
        portal_data = data.get("portal", {}) or {}
        portal = PortalQuirks(
            accepts_markdown=bool(portal_data.get("accepts_markdown", True)),
            plain_text_boxes=bool(portal_data.get("plain_text_boxes", False)),
            url=portal_data.get("url"),
            notes=portal_data.get("notes"),
        )
        rubric = [
            RubricCriterion(
                id=c.get("id", ""),
                name=c.get("name", c.get("id", "")),
                description=c.get("description"),
                citation=c.get("citation"),
                url=c.get("url"),
            )
            for c in data.get("review_rubric", []) or []
        ]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            program=data.get("program"),
            version=data.get("version"),
            source_url=data.get("source_url"),
            extends=data.get("extends"),
            locale=data.get("locale", "en-US"),
            provenance=data.get("provenance"),
            content_engine=data.get("content_engine"),
            sections=sections,
            formatting_rules=rules,
            budget_rules=budget_rules,
            proposal_rules=proposal_rules,
            attachment_groups=attachment_groups,
            portal=portal,
            review_rubric=rubric,
            raw=data,
        )


def _is_int_or_none(value: Any) -> bool:
    return value is None or (
        isinstance(value, int) and not isinstance(value, bool)
    )


def _is_string(value: Any, *, nonempty: bool = False) -> TypeGuard[str]:
    if not isinstance(value, str) or (nonempty and not value):
        return False
    if any(
        (ord(char) < 32 and char not in "\t\n\r") or 0x7F <= ord(char) <= 0x9F
        for char in value
    ):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _is_string_or_none(value: Any) -> bool:
    return value is None or _is_string(value)


def _is_number_or_none(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_pack(data: Any) -> list[str]:
    """Validate a raw rule-pack dict against the schema.

    Returns a list of error strings. An empty list means the pack is valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["pack must be a mapping/dict"]

    # Required top-level keys
    for key in ("id", "name"):
        if not _is_string(data.get(key), nonempty=True):
            errors.append(f"missing required key: '{key}'")

    for key in ("program", "version", "source_url", "provenance"):
        if not _is_string_or_none(data.get(key)):
            errors.append(f"'{key}' must be a string or null")
    if "extends" in data and not _is_string(
        data.get("extends"), nonempty=True
    ):
        errors.append("'extends' must be a non-empty string")

    locale = data.get("locale", "en-US")
    if not _is_string(locale) or locale not in VALID_LOCALES:
        errors.append(
            f"invalid locale {locale!r} (allowed: {sorted(VALID_LOCALES)})"
        )

    content_engine = data.get("content_engine")
    if (
        content_engine is not None and not _is_string(content_engine)
    ) or content_engine not in VALID_CONTENT_ENGINES:
        errors.append(
            f"invalid content_engine {content_engine!r} "
            f"(allowed: {sorted(str(e) for e in VALID_CONTENT_ENGINES)})"
        )

    # Sections
    sections = data.get("sections", [])
    if sections is not None and not isinstance(sections, list):
        errors.append("'sections' must be a list")
    else:
        seen_ids: set[str] = set()
        for i, section in enumerate(sections or []):
            where = f"sections[{i}]"
            if not isinstance(section, dict):
                errors.append(f"{where} must be a mapping")
                continue
            sid = section.get("id")
            if not _is_string(sid, nonempty=True):
                errors.append(f"{where} missing 'id'")
            elif sid in seen_ids:
                errors.append(f"{where} duplicate section id '{sid}'")
            else:
                seen_ids.add(sid)
            if not _is_string(section.get("title"), nonempty=True):
                errors.append(f"{where} ('{sid}') missing 'title'")
            for key in ("description", "file", "stage"):
                if not _is_string_or_none(section.get(key)):
                    errors.append(
                        f"{where} ('{sid}') '{key}' must be a string or null"
                    )
            for limit_key in ("word_limit", "char_limit", "page_limit"):
                if not _is_int_or_none(section.get(limit_key)):
                    errors.append(
                        f"{where} ('{sid}') '{limit_key}' must be an integer or null"
                    )
            if "required" in section and not isinstance(
                section["required"], bool
            ):
                errors.append(
                    f"{where} ('{sid}') 'required' must be a boolean"
                )
            if "format" in section and (
                not _is_string(section["format"])
                or section["format"] not in VALID_SECTION_FORMATS
            ):
                errors.append(
                    f"{where} ('{sid}') invalid format "
                    f"{section['format']!r} "
                    f"(allowed: {sorted(VALID_SECTION_FORMATS)})"
                )

    # Formatting rules
    rules = data.get("formatting_rules", [])
    if rules is not None and not isinstance(rules, list):
        errors.append("'formatting_rules' must be a list")
    else:
        for i, rule in enumerate(rules or []):
            where = f"formatting_rules[{i}]"
            if not isinstance(rule, dict):
                errors.append(f"{where} must be a mapping")
                continue
            if not _is_string(rule.get("id"), nonempty=True):
                errors.append(f"{where} missing 'id'")
            if not _is_string(rule.get("description"), nonempty=True):
                errors.append(
                    f"{where} ('{rule.get('id')}') missing 'description'"
                )
            severity = rule.get("severity", "error")
            if not _is_string(severity) or severity not in VALID_SEVERITIES:
                errors.append(
                    f"{where} ('{rule.get('id')}') invalid severity "
                    f"{severity!r} "
                    f"(allowed: {sorted(VALID_SEVERITIES)})"
                )
            for key in ("citation", "url", "quote"):
                if not _is_string_or_none(rule.get(key)):
                    errors.append(
                        f"{where} ('{rule.get('id')}') '{key}' must be a "
                        "string or null"
                    )
            applies_to = rule.get("applies_to", "all")
            if not _is_string(applies_to, nonempty=True):
                errors.append(
                    f"{where} ('{rule.get('id')}') 'applies_to' must be a "
                    "non-empty string"
                )

    # Budget rules
    budget = data.get("budget_rules")
    if budget is not None:
        if not isinstance(budget, dict):
            errors.append("'budget_rules' must be a mapping")
        else:
            for key in ("total_cap", "annual_cap", "indirect_rate_max"):
                if not _is_number_or_none(budget.get(key)):
                    errors.append(
                        f"budget_rules.{key} must be a number or null"
                    )
            if budget.get("mtdc_excludes") is not None and not isinstance(
                budget.get("mtdc_excludes"), list
            ):
                errors.append("budget_rules.mtdc_excludes must be a list")
            elif not all(
                _is_string(entry, nonempty=True)
                for entry in budget.get("mtdc_excludes", []) or []
            ):
                errors.append(
                    "budget_rules.mtdc_excludes must contain non-empty strings"
                )
            if not _is_string(budget.get("currency", "USD"), nonempty=True):
                errors.append(
                    "budget_rules.currency must be a non-empty string"
                )
            if not _is_string_or_none(budget.get("notes")):
                errors.append("budget_rules.notes must be a string or null")

            preparation = budget.get("preparation")
            if preparation is not None:
                if not isinstance(preparation, dict):
                    errors.append("budget_rules.preparation must be a mapping")
                else:
                    _validate_budget_preparation_rules(preparation, errors)

    # Proposal-wide rules
    proposal = data.get("proposal_rules")
    if proposal is not None:
        if not isinstance(proposal, dict):
            errors.append("'proposal_rules' must be a mapping")
        else:
            title_prefix = proposal.get("title_prefix")
            if title_prefix is not None and not _is_string(
                title_prefix, nonempty=True
            ):
                errors.append(
                    "proposal_rules.title_prefix must be a non-empty string "
                    "or null"
                )
            if not _is_string_or_none(proposal.get("citation")):
                errors.append(
                    "proposal_rules.citation must be a string or null"
                )
            duration = proposal.get("max_duration_months")
            if not _is_int_or_none(duration) or (
                isinstance(duration, int) and duration < 1
            ):
                errors.append(
                    "proposal_rules.max_duration_months must be a positive "
                    "integer or null"
                )

    # Attachment groups
    groups = data.get("attachment_groups", [])
    if groups is not None and not isinstance(groups, list):
        errors.append("'attachment_groups' must be a list")
    else:
        seen_group_ids: set[str] = set()
        for i, group in enumerate(groups or []):
            where = f"attachment_groups[{i}]"
            if not isinstance(group, dict):
                errors.append(f"{where} must be a mapping")
                continue
            gid = group.get("id")
            if not _is_string(gid, nonempty=True):
                errors.append(f"{where} missing 'id'")
            elif gid in seen_group_ids:
                errors.append(f"{where} duplicate id '{gid}'")
            else:
                seen_group_ids.add(gid)
            for key in ("title", "glob"):
                if not _is_string(group.get(key), nonempty=True):
                    errors.append(f"{where} ('{gid}') missing '{key}'")
            for key in ("min_count", "max_count", "page_limit_each"):
                value = group.get(key, 0 if key == "min_count" else None)
                if not _is_int_or_none(value) or (
                    isinstance(value, int) and value < 0
                ):
                    errors.append(
                        f"{where} ('{gid}') '{key}' must be a "
                        "non-negative integer or null"
                    )
            page_limit = group.get("page_limit_each")
            if isinstance(page_limit, int) and page_limit == 0:
                errors.append(
                    f"{where} ('{gid}') 'page_limit_each' must be a "
                    "positive integer or null"
                )
            glob = group.get("glob")
            if isinstance(glob, str):
                parts = glob.replace("\\", "/").split("/")
                if glob.startswith("/") or ".." in parts:
                    errors.append(
                        f"{where} ('{gid}') 'glob' must stay within the "
                        "grant project"
                    )
            minimum = group.get("min_count", 0)
            maximum = group.get("max_count")
            if (
                isinstance(minimum, int)
                and isinstance(maximum, int)
                and maximum < minimum
            ):
                errors.append(
                    f"{where} ('{gid}') max_count must be >= min_count"
                )
            if not _is_string_or_none(group.get("citation")):
                errors.append(
                    f"{where} ('{gid}') 'citation' must be a string or null"
                )

    # Portal
    portal = data.get("portal")
    if portal is not None:
        if not isinstance(portal, dict):
            errors.append("'portal' must be a mapping")
        else:
            for key in ("accepts_markdown", "plain_text_boxes"):
                if key in portal and not isinstance(portal[key], bool):
                    errors.append(f"portal.{key} must be a boolean")
            for key in ("url", "notes"):
                if not _is_string_or_none(portal.get(key)):
                    errors.append(f"portal.{key} must be a string or null")

    # Review rubric
    rubric = data.get("review_rubric", [])
    if rubric is not None and not isinstance(rubric, list):
        errors.append("'review_rubric' must be a list")
    else:
        for i, crit in enumerate(rubric or []):
            where = f"review_rubric[{i}]"
            if not isinstance(crit, dict):
                errors.append(f"{where} must be a mapping")
                continue
            if not _is_string(crit.get("id"), nonempty=True):
                errors.append(f"{where} missing 'id'")
            if not _is_string(crit.get("name"), nonempty=True):
                errors.append(f"{where} ('{crit.get('id')}') missing 'name'")
            for key in ("description", "citation", "url"):
                if not _is_string_or_none(crit.get(key)):
                    errors.append(
                        f"{where} ('{crit.get('id')}') '{key}' must be a "
                        "string or null"
                    )

    return errors


def _validate_budget_preparation_rules(
    preparation: dict[str, Any], errors: list[str]
) -> None:
    """Validate the structured budget-preparation sub-contract."""
    prefix = "budget_rules.preparation"

    for key in (
        "institutional_salary_org_types",
        "bls_salary_org_types",
        "fringe_justification_fields",
        "consultant_justification_fields",
        "equity_owner_payment_channels",
        "icorps_required_team_roles",
        "icorps_allowed_cost_types",
        "icorps_prohibited_cost_types",
        "icorps_current_salary_cap_roles",
    ):
        value = preparation.get(key, [])
        if not isinstance(value, list) or not all(
            _is_string(item, nonempty=True) for item in value
        ):
            errors.append(
                f"{prefix}.{key} must be a list of non-empty strings"
            )

    for key in (
        "lines_ab_employee_only",
        "personnel_justification_fields_required",
        "main_equipment_necessity_required",
        "subaward_detail_required",
        "subaward_ip_rights_agreement_required",
        "line_g_services_description_required",
        "indirect_base_amount_verification_required",
        "icorps_domestic_travel_only",
        "icorps_team_agreement_required",
    ):
        if key in preparation and not isinstance(preparation[key], bool):
            errors.append(f"{prefix}.{key} must be a boolean")

    allowed_equity_channels = {"consultant", "contractor", "subaward"}
    equity_channels = preparation.get("equity_owner_payment_channels", [])
    if isinstance(equity_channels, list) and any(
        isinstance(item, str) and item not in allowed_equity_channels
        for item in equity_channels
    ):
        errors.append(
            f"{prefix}.equity_owner_payment_channels contains an unknown "
            "channel"
        )

    if "subaward_equipment_allowed" in preparation and not isinstance(
        preparation["subaward_equipment_allowed"], bool
    ):
        errors.append(f"{prefix}.subaward_equipment_allowed must be a boolean")

    percentile = preparation.get("bls_salary_percentile")
    if not _is_number_or_none(percentile) or (
        isinstance(percentile, (int, float))
        and not isinstance(percentile, bool)
        and not 0 < percentile <= 100
    ):
        errors.append(
            f"{prefix}.bls_salary_percentile must be between 0 and 100 or null"
        )

    for key in (
        "salary_months_justification_threshold",
        "salary_hourly_month_hours",
        "consultant_statement_threshold",
        "icorps_budget_cap",
    ):
        value = preparation.get(key)
        if not _is_number_or_none(value) or (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value < 0
        ):
            errors.append(f"{prefix}.{key} must be non-negative or null")

    for key in ("max_budget_years", "icorps_team_size_manual_review_max"):
        value = preparation.get(key)
        if not _is_int_or_none(value) or (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value < 1
        ):
            errors.append(f"{prefix}.{key} must be a positive integer or null")

    fraction = preparation.get("materials_explanation_threshold_fraction")
    if not _is_number_or_none(fraction) or (
        isinstance(fraction, (int, float))
        and not isinstance(fraction, bool)
        and not 0 < fraction <= 1
    ):
        errors.append(
            f"{prefix}.materials_explanation_threshold_fraction must be "
            "between 0 and 1 or null"
        )

    rate = preparation.get("de_minimis_indirect_rate")
    if not _is_number_or_none(rate) or (
        isinstance(rate, (int, float))
        and not isinstance(rate, bool)
        and not 0 <= rate <= 1
    ):
        errors.append(
            f"{prefix}.de_minimis_indirect_rate must be between 0 and 1 or null"
        )

    travel_format = preparation.get("travel_breakdown_format")
    if travel_format not in (None, "table"):
        errors.append(
            f"{prefix}.travel_breakdown_format must be 'table' or null"
        )

    travel_cost_rules = preparation.get("travel_cost_rules", {})
    if not isinstance(travel_cost_rules, dict) or not all(
        _is_string(key, nonempty=True) and _is_string(value, nonempty=True)
        for key, value in travel_cost_rules.items()
    ):
        errors.append(
            f"{prefix}.travel_cost_rules must be a string-to-string mapping"
        )

    for key in (
        "de_minimis_indirect_base",
        "icorps_training_format",
        "icorps_context_url",
        "citation",
        "url",
    ):
        if not _is_string_or_none(preparation.get(key)):
            errors.append(f"{prefix}.{key} must be a string or null")

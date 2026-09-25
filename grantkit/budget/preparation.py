"""Declarative validation for funder budget-preparation requirements.

The arithmetic calculator intentionally accepts a compact legacy ``budget.yaml``
shape.  This module validates additional source-backed evidence only when a
funder pack declares a ``budget_rules.preparation`` contract.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

from ..packs.schema import BudgetPreparationRules


@dataclass(frozen=True)
class BudgetPreparationFinding:
    """One budget-preparation finding for conversion to a core CheckItem."""

    level: str
    rule: str
    message: str


def validate_budget_preparation(
    data: dict[str, Any],
    rules: BudgetPreparationRules,
    *,
    project_root: Path,
    grand_total: Optional[float],
    budget_justification: str,
    icorps_required: bool = False,
    declared_icorps_budget_amount: Optional[float] = None,
) -> list[BudgetPreparationFinding]:
    """Validate ``budget.yaml`` against a pack's preparation contract."""
    findings: list[BudgetPreparationFinding] = []
    years = _budget_years(data)
    findings += _validate_nonnegative_budget_amounts(data)
    findings += _validate_budget_period(data, rules)
    findings += _validate_budget_year_allocations(data, years)
    people = list(_iter_personnel(data))

    organization_type = _normalize_token(data.get("organization_type"))
    if not organization_type:
        findings.append(
            _error(
                "pesose_budget_organization_type_missing",
                "budget.yaml must declare organization_type so PESOSE salary "
                "and travel rules can be applied. Organization types are not "
                "treated as a closed eligibility list.",
            )
        )

    bls_types = {
        _normalize_token(value) for value in rules.bls_salary_org_types
    }
    institutional_types = {
        _normalize_token(value)
        for value in rules.institutional_salary_org_types
    }
    if organization_type and organization_type not in (
        bls_types | institutional_types
    ):
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_budget_salary_route_manual_review",
                message=(
                    f"organization_type '{organization_type}' is valid but is "
                    "not assigned a salary-rate route in the PESOSE update. "
                    "Confirm the applicable treatment with NSF."
                ),
            )
        )
    for line, index, person in people:
        label = _person_label(person, line, index)
        if (
            rules.lines_ab_employee_only
            and person.get("employee_of_proposing_organization") is not True
        ):
            findings.append(
                _error(
                    "pesose_budget_employee_only",
                    f"{label} on Line {line} must explicitly attest "
                    "employee_of_proposing_organization: true.",
                )
            )

        if rules.personnel_justification_fields_required:
            findings += _validate_personnel_justification(
                person, label, years, rules
            )

        if organization_type in institutional_types:
            findings += _validate_institutional_salary(person, label)

        if organization_type in bls_types:
            findings += _validate_bls_person(person, label, rules)

        threshold = rules.salary_months_justification_threshold
        if threshold is not None:
            findings += _validate_cumulative_nsf_months(
                person, label, years, threshold
            )

    findings += _validate_fringe(data, rules, years)
    findings += _validate_equipment(data, rules, years)
    findings += _validate_travel(
        data,
        rules,
        years,
        budget_justification,
        organization_type,
    )
    findings += _validate_materials(data, rules, years, grand_total)
    findings += _validate_other_direct_costs(data, rules, years, project_root)
    findings += _validate_indirect_costs(data, rules, years)
    findings += _validate_icorps(
        data,
        rules,
        years,
        required=icorps_required,
        declared_amount=declared_icorps_budget_amount,
    )
    return findings


def _validate_personnel_justification(
    person: dict[str, Any],
    label: str,
    years: int,
    rules: BudgetPreparationRules,
) -> list[BudgetPreparationFinding]:
    """Check the fields NSF requires for every main-budget Line A/B person."""
    findings: list[BudgetPreparationFinding] = []
    missing = []
    if not (_nonempty(person.get("title")) or _nonempty(person.get("role"))):
        missing.append("title (or role)")
    if (
        _number(person.get("requested_salary_rate", person.get("base_salary")))
        is None
    ):
        missing.append("requested_salary_rate (or base_salary)")
    if not _nonempty(person.get("responsibilities")):
        missing.append("responsibilities")
    calendar_months = _year_values(person.get("calendar_months"), years)
    if calendar_months is None:
        missing.append("calendar_months for every budget year")
    total_requested = _number(person.get("total_requested_salary"))
    if total_requested is None:
        missing.append("total_requested_salary")
    if missing:
        findings.append(
            _error(
                "pesose_budget_personnel_justification_fields",
                f"{label} must provide Line A/B budget-justification fields: "
                + ", ".join(missing)
                + ".",
            )
        )

    if (
        person.get("budget_justification_includes_personnel_details")
        is not True
    ):
        findings.append(
            _error(
                "pesose_budget_personnel_justification_attestation",
                f"{label} must attest "
                "budget_justification_includes_personnel_details: true so "
                "the YAML evidence is tied to the submitted justification.",
            )
        )
    if (
        person.get("calendar_months_reflect_requested_person_months")
        is not True
    ):
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_budget_calendar_months_attestation",
                message=(
                    f"{label} should attest "
                    "calendar_months_reflect_requested_person_months: true."
                ),
            )
        )

    budgeted_total = _budgeted_line_total(person, years)
    if (
        total_requested is not None
        and budgeted_total is not None
        and not math.isclose(total_requested, budgeted_total, abs_tol=1)
    ):
        findings.append(
            _error(
                "pesose_budget_personnel_total_mismatch",
                f"{label}'s total_requested_salary does not match the "
                "year-by-year salary request.",
            )
        )

    basis = _normalize_token(person.get("salary_calculation_basis"))
    annual_rates_value = person.get("annual_salary_rate_by_year")
    if annual_rates_value is not None:
        annual_rates = _year_values(annual_rates_value, years)
        if annual_rates is None or any(rate <= 0 for rate in annual_rates):
            findings.append(
                _error(
                    "pesose_budget_annual_salary_rates_invalid",
                    f"{label}'s optional annual_salary_rate_by_year must "
                    "provide a positive rate for every budget year.",
                )
            )
        elif calendar_months is not None and basis == "salary":
            requested_by_year = [
                _number(person.get(f"year_{year}"))
                for year in range(1, years + 1)
            ]
            if all(
                amount is not None and amount >= 0
                for amount in requested_by_year
            ):
                mismatches = []
                for year, (actual, requested, annual_rate) in enumerate(
                    zip(calendar_months, requested_by_year, annual_rates),
                    start=1,
                ):
                    assert requested is not None
                    expected = 12 * float(requested) / annual_rate
                    if not math.isclose(
                        actual, expected, rel_tol=0.005, abs_tol=0.01
                    ):
                        mismatches.append(f"year_{year}")
                if mismatches:
                    findings.append(
                        BudgetPreparationFinding(
                            level="warning",
                            rule="pesose_budget_calendar_months_mismatch",
                            message=(
                                f"{label}'s calendar_months should match "
                                "requested salary and "
                                "annual_salary_rate_by_year for: "
                                + ", ".join(mismatches)
                                + "."
                            ),
                        )
                    )
    if basis not in {"salary", "hourly"}:
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_budget_173_33_hours_manual_review",
                message=(
                    f"Declare {label}'s salary_calculation_basis as salary or "
                    "hourly so the 173.33-hours-per-month rule can be applied "
                    "where appropriate."
                ),
            )
        )
    elif basis == "hourly" and rules.salary_hourly_month_hours is not None:
        hours = _number(person.get("hours_per_month"))
        if hours is None or not math.isclose(
            hours, rules.salary_hourly_month_hours, abs_tol=0.005
        ):
            findings.append(
                _error(
                    "pesose_budget_173_33_hours",
                    f"{label}'s hourly salary calculation must use "
                    f"{rules.salary_hourly_month_hours:g} hours per month.",
                )
            )
    return findings


def _validate_institutional_salary(
    person: dict[str, Any], label: str
) -> list[BudgetPreparationFinding]:
    """Validate IHE/state/local existing- and new-employee salary routes."""
    status = _normalize_token(person.get("employment_status"))
    if status not in {"existing", "new"}:
        return [
            _error(
                "pesose_budget_employment_status",
                f"{label} must declare employment_status: existing or new.",
            )
        ]

    if status == "new":
        missing = []
        if (
            person.get("salary_rate_consistent_with_written_policy")
            is not True
        ):
            missing.append("salary_rate_consistent_with_written_policy: true")
        if (
            person.get("escalation_rates_consistent_with_written_policy")
            is not True
        ):
            missing.append(
                "escalation_rates_consistent_with_written_policy: true"
            )
        if not missing:
            return []
        return [
            _error(
                "pesose_budget_new_employee_written_policy",
                f"{label}'s new-employee salary and escalation rates need "
                "written-policy attestations: " + ", ".join(missing) + ".",
            )
        ]

    findings: list[BudgetPreparationFinding] = []
    rate_attestation = person.get(
        "requested_rate_no_greater_than_current_attestation"
    )
    if rate_attestation is False:
        findings.append(
            _error(
                "pesose_budget_existing_employee_rate",
                f"{label} cannot request an institutional salary rate above "
                "the current salary rate.",
            )
        )
    missing = []
    if rate_attestation is not True:
        missing.append("current-rate cap statement")
    if not _nonempty(person.get("anticipated_institutional_escalation_rates")):
        missing.append("anticipated_institutional_escalation_rates")
    if missing:
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_budget_existing_employee_salary_statement",
                message=(
                    f"{label}'s existing-employee budget justification "
                    "should include: " + ", ".join(missing) + "."
                ),
            )
        )
    return findings


def _validate_bls_person(
    person: dict[str, Any],
    label: str,
    rules: BudgetPreparationRules,
) -> list[BudgetPreparationFinding]:
    findings: list[BudgetPreparationFinding] = []
    soc = person.get("soc_code")
    if not isinstance(soc, str) or not re.fullmatch(r"\d{2}-\d{4}", soc):
        findings.append(
            _error(
                "pesose_budget_soc_code",
                f"{label} must provide a SOC code in NN-NNNN format.",
            )
        )

    bls_url = person.get("bls_url")
    if not _is_bls_url(bls_url):
        findings.append(
            _error(
                "pesose_budget_bls_url",
                f"{label} must provide an HTTPS link to the relevant "
                "bls.gov page; run grantkit check --urls to test liveness.",
            )
        )

    evidence_missing = []
    if person.get("bls_benchmark_is_non_c_level") is not True:
        evidence_missing.append("bls_benchmark_is_non_c_level: true")
    if person.get("soc_responsibilities_match") is not True:
        evidence_missing.append("soc_responsibilities_match: true")
    if not _nonempty(person.get("work_location")):
        evidence_missing.append("work_location")
    if not _nonempty(person.get("bls_geographic_area")):
        evidence_missing.append("bls_geographic_area")
    if person.get("bls_geography_matches_work_location") is not True:
        evidence_missing.append("bls_geography_matches_work_location: true")
    if evidence_missing:
        findings.append(
            _error(
                "pesose_budget_bls_match_attestations",
                f"{label}'s BLS benchmark must use responsibilities and the "
                "work location, not a C-level role; provide: "
                + ", ".join(evidence_missing)
                + ".",
            )
        )

    requested = _number(
        person.get("requested_salary_rate", person.get("base_salary"))
    )
    benchmark = _number(person.get("bls_percentile_rate"))
    percentile = rules.bls_salary_percentile
    percentile_label = (
        f"{percentile:g}th" if percentile is not None else "configured"
    )
    if requested is None or requested < 0:
        findings.append(
            _error(
                "pesose_budget_salary_rate",
                f"{label} must provide a non-negative requested_salary_rate "
                "(or base_salary).",
            )
        )
    if benchmark is None or benchmark <= 0:
        findings.append(
            _error(
                "pesose_budget_bls_percentile_rate",
                f"{label} must provide the relevant BLS {percentile_label}-"
                "percentile rate as bls_percentile_rate.",
            )
        )
    if (
        requested is not None
        and benchmark is not None
        and requested > benchmark
        and not _nonempty(person.get("above_bls_percentile_justification"))
    ):
        findings.append(
            _error(
                "pesose_budget_bls_justification",
                f"{label}'s requested salary rate exceeds the BLS "
                f"{percentile_label} percentile and needs a strong "
                "above_bls_percentile_justification.",
            )
        )
    return findings


def _validate_cumulative_nsf_months(
    person: dict[str, Any],
    label: str,
    years: int,
    threshold: float,
) -> list[BudgetPreparationFinding]:
    if "cumulative_nsf_person_months" not in person:
        return [
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_budget_nsf_months_manual_review",
                message=(
                    f"Confirm {label}'s cumulative NSF salary support by "
                    "award year, or declare cumulative_nsf_person_months so "
                    f"GrantKit can test the {threshold:g}-month threshold."
                ),
            )
        ]

    value = person["cumulative_nsf_person_months"]
    month_values = _month_values(value, years)
    if month_values is None:
        return [
            _error(
                "pesose_budget_nsf_months_invalid",
                f"{label}'s cumulative_nsf_person_months must be a "
                "non-negative number for a one-year budget or a non-empty "
                "year-to-month mapping.",
            )
        ]
    if any(months > threshold for months in month_values) and not _nonempty(
        person.get("over_two_months_justification")
    ):
        return [
            _error(
                "pesose_budget_over_two_months_justification",
                f"{label} exceeds {threshold:g} cumulative NSF person-months "
                "in at least one year and needs an explicit "
                "over_two_months_justification.",
            )
        ]
    return []


def _validate_fringe(
    data: dict[str, Any], rules: BudgetPreparationRules, years: int
) -> list[BudgetPreparationFinding]:
    fringe = data.get("fringe_benefits")
    if not isinstance(fringe, dict) or not _mapping_has_funding(fringe, years):
        return []
    findings: list[BudgetPreparationFinding] = []
    missing = [
        field
        for field in rules.fringe_justification_fields
        if not _nonempty(fringe.get(field))
    ]
    if missing:
        findings.append(
            _error(
                "pesose_budget_fringe_fields",
                "Funded fringe benefits must provide budget-justification "
                "fields: " + ", ".join(missing) + ".",
            )
        )
    if fringe.get("budget_justification_includes_fringe_details") is not True:
        findings.append(
            _error(
                "pesose_budget_fringe_justification_attestation",
                "Funded fringe benefits must attest "
                "budget_justification_includes_fringe_details: true.",
            )
        )
    return findings


def _validate_equipment(
    data: dict[str, Any], rules: BudgetPreparationRules, years: int
) -> list[BudgetPreparationFinding]:
    if not rules.main_equipment_necessity_required:
        return []
    equipment = data.get("equipment", [])
    if not isinstance(equipment, list):
        return []
    findings: list[BudgetPreparationFinding] = []
    for index, item in enumerate(equipment):
        if not isinstance(item, dict) or not _mapping_has_funding(item, years):
            continue
        if not _nonempty(item.get("necessity")):
            findings.append(
                _error(
                    "pesose_budget_equipment_necessity",
                    f"Main-budget equipment item {index + 1} must explain "
                    "why the equipment is necessary.",
                )
            )
        if not _nonempty(item.get("description")):
            findings.append(
                BudgetPreparationFinding(
                    level="warning",
                    rule="pesose_budget_equipment_description",
                    message=(
                        f"Main-budget equipment item {index + 1}'s budget "
                        "justification should describe the equipment."
                    ),
                )
            )
        if (
            item.get("budget_justification_includes_description_and_necessity")
            is not True
        ):
            findings.append(
                BudgetPreparationFinding(
                    level="warning",
                    rule="pesose_budget_equipment_justification_attestation",
                    message=(
                        f"Main-budget equipment item {index + 1}'s budget "
                        "justification should include its description and "
                        "necessity."
                    ),
                )
            )
    return findings


def _validate_travel(
    data: dict[str, Any],
    rules: BudgetPreparationRules,
    years: int,
    budget_justification: str,
    organization_type: str,
) -> list[BudgetPreparationFinding]:
    trips = list(_iter_trips(data))
    if not trips:
        return []
    findings: list[BudgetPreparationFinding] = []
    for kind, index, trip in trips:
        if not _mapping_has_funding(trip, years):
            continue
        label = trip.get("description") or f"{kind} trip {index + 1}"
        missing = [
            field
            for field in ("description", "necessity")
            if not _nonempty(trip.get(field))
        ]
        if missing:
            findings.append(
                _error(
                    "pesose_budget_travel_justification",
                    f"{label} must provide: " + ", ".join(missing) + ".",
                )
            )
        if (
            trip.get(
                "budget_justification_includes_description_necessity_and_breakdown"
            )
            is not True
        ):
            findings.append(
                _error(
                    "pesose_budget_travel_justification_attestation",
                    f"{label} must attest budget_justification_includes_"
                    "description_necessity_and_breakdown: true.",
                )
            )
        breakdown = trip.get("breakdown")
        if not isinstance(breakdown, (dict, list)) or not breakdown:
            findings.append(
                _error(
                    "pesose_budget_travel_breakdown",
                    f"{label} needs a non-empty, itemized breakdown.",
                )
            )
        expected_cost_rule = rules.travel_cost_rules.get(
            organization_type, rules.travel_cost_rules.get("default")
        )
        actual_cost_rule = _normalize_token(trip.get("cost_rule"))
        if expected_cost_rule and actual_cost_rule != _normalize_token(
            expected_cost_rule
        ):
            findings.append(
                _error(
                    "pesose_budget_travel_cost_rule",
                    f"{label} must identify cost_rule: {expected_cost_rule}.",
                )
            )

    funded_trips = [
        trip for _, _, trip in trips if _mapping_has_funding(trip, years)
    ]
    if funded_trips and rules.travel_breakdown_format == "table":
        if not _has_markdown_table(budget_justification):
            findings.append(
                _error(
                    "pesose_budget_travel_table",
                    "The Budget Justification must contain a Markdown table "
                    "with a detailed funding breakdown for each funded trip.",
                )
            )
        attestations = data.get("budget_justification_attestations", {})
        if (
            not isinstance(attestations, dict)
            or attestations.get("travel_breakdown_covers_each_trip")
            is not True
        ):
            findings.append(
                _error(
                    "pesose_budget_travel_table_attestation",
                    "Attest budget_justification_attestations."
                    "travel_breakdown_covers_each_trip: true.",
                )
            )
    return findings


def _validate_materials(
    data: dict[str, Any],
    rules: BudgetPreparationRules,
    years: int,
    grand_total: Optional[float],
) -> list[BudgetPreparationFinding]:
    threshold = rules.materials_explanation_threshold_fraction
    if threshold is None:
        return []
    materials = sum(
        _line_total(item, years)
        for item in _other_direct_costs(data)
        if _is_materials_item(item)
    )
    if (
        grand_total is None
        or grand_total <= 0
        or materials <= threshold * grand_total
    ):
        return []
    attestations = data.get("budget_justification_attestations", {})
    if (
        isinstance(attestations, dict)
        and attestations.get("materials_and_supplies_need_explained") is True
    ):
        return []
    return [
        _error(
            "pesose_budget_materials_justification",
            f"Materials and supplies are {materials / grand_total:.1%} of "
            f"the total budget, above {threshold:.0%}; attest that the Budget "
            "Justification explains their need.",
        )
    ]


def _validate_other_direct_costs(
    data: dict[str, Any],
    rules: BudgetPreparationRules,
    years: int,
    project_root: Path,
) -> list[BudgetPreparationFinding]:
    findings: list[BudgetPreparationFinding] = []
    channels = set(rules.equity_owner_payment_channels)
    for index, item in enumerate(_other_direct_costs(data)):
        channel = _payment_channel(item)
        label = (
            item.get("description")
            or item.get("institution")
            or (f"other_direct_costs item {index + 1}")
        )
        if channel is not None and channel in channels:
            equity = item.get("payee_is_owner_or_equity_holder")
            if equity is None:
                findings.append(
                    _error(
                        "pesose_budget_equity_owner_attestation",
                        f"{label} must explicitly attest "
                        "payee_is_owner_or_equity_holder: false.",
                    )
                )
            elif equity is not False:
                findings.append(
                    _error(
                        "pesose_budget_equity_owner_prohibited",
                        f"{label} cannot be paid through a {channel} because "
                        "the payee is an owner of, or equity holder in, the "
                        "proposing entity.",
                    )
                )

        if channel == "consultant":
            findings += _validate_consultant_justification(
                item, str(label), years, rules
            )
            threshold = rules.consultant_statement_threshold
            if threshold is not None and _line_total(item, years) > threshold:
                findings += _validate_consultant_statement(
                    item, str(label), project_root
                )

        if channel == "subaward":
            if rules.subaward_detail_required:
                findings += _validate_subaward_detail(
                    item, str(label), years, project_root
                )
            if rules.subaward_ip_rights_agreement_required:
                findings += _validate_ip_agreement(
                    item, str(label), project_root
                )
            if rules.subaward_equipment_allowed is False and (
                _declares_equipment(item.get("equipment"))
                or _declares_equipment(item.get("equipment_amount"))
            ):
                findings.append(
                    _error(
                        "pesose_budget_subaward_equipment_prohibited",
                        f"{label} requests equipment on a subaward budget; "
                        "PESOSE does not allow subaward equipment.",
                    )
                )
        if (
            rules.line_g_services_description_required
            and _is_line_g_services_item(item, channel)
            and not _nonempty(item.get("services_description"))
        ):
            findings.append(
                _error(
                    "pesose_budget_line_g_services_description",
                    f"{label} must describe the services requested on Line G.",
                )
            )
        if (
            rules.line_g_services_description_required
            and _is_line_g_services_item(item, channel)
            and item.get("budget_justification_includes_services_description")
            is not True
        ):
            findings.append(
                _error(
                    "pesose_budget_line_g_services_attestation",
                    f"{label} must attest budget_justification_includes_"
                    "services_description: true.",
                )
            )
    return findings


def _validate_consultant_justification(
    item: dict[str, Any],
    label: str,
    years: int,
    rules: BudgetPreparationRules,
) -> list[BudgetPreparationFinding]:
    missing = []
    for field in rules.consultant_justification_fields:
        value = item.get(field)
        if field in {"consultant_rate", "total_requested"}:
            if _number(value) is None:
                missing.append(field)
        elif not _nonempty(value):
            missing.append(field)
    findings: list[BudgetPreparationFinding] = []
    if missing:
        findings.append(
            _error(
                "pesose_budget_consultant_justification_fields",
                f"{label} must provide consultant budget-justification fields: "
                + ", ".join(missing)
                + ".",
            )
        )
    if (
        item.get("budget_justification_includes_consultant_details")
        is not True
    ):
        findings.append(
            _error(
                "pesose_budget_consultant_justification_attestation",
                f"{label} must attest "
                "budget_justification_includes_consultant_details: true.",
            )
        )
    declared = _number(item.get("total_requested"))
    budgeted = _budgeted_line_total(item, years)
    if (
        declared is not None
        and budgeted is not None
        and not math.isclose(declared, budgeted, abs_tol=1)
    ):
        findings.append(
            _error(
                "pesose_budget_consultant_total_mismatch",
                f"{label}'s total_requested does not match its budgeted amount.",
            )
        )
    return findings


def _validate_subaward_detail(
    item: dict[str, Any],
    label: str,
    years: int,
    project_root: Path,
) -> list[BudgetPreparationFinding]:
    findings: list[BudgetPreparationFinding] = []
    missing = [
        field
        for field in ("purpose", "key_tasks")
        if not _nonempty(item.get(field))
    ]
    requested = _number(item.get("requested_funding_amount"))
    if requested is None:
        missing.append("requested_funding_amount")
    if missing:
        findings.append(
            _error(
                "pesose_budget_subaward_justification_fields",
                f"{label} must provide subaward purpose, tasks, and amount: "
                + ", ".join(missing)
                + ".",
            )
        )
    if item.get("budget_justification_includes_subaward_details") is not True:
        findings.append(
            _error(
                "pesose_budget_subaward_justification_attestation",
                f"{label} must attest "
                "budget_justification_includes_subaward_details: true.",
            )
        )
    budgeted = _budgeted_line_total(item, years)
    if (
        requested is not None
        and budgeted is not None
        and not math.isclose(requested, budgeted, abs_tol=1)
    ):
        findings.append(
            _error(
                "pesose_budget_subaward_amount_mismatch",
                f"{label}'s requested_funding_amount does not match its "
                "budgeted amount.",
            )
        )

    statement = item.get("subaward_pi_statement")
    statement_fields = (
        "included_in_budget_justification",
        "signed_by_business_office",
        "confirms_willingness",
        "describes_responsibilities",
    )
    if not isinstance(statement, dict):
        statement_missing = list(statement_fields)
    else:
        statement_missing = []
        statement_file = statement.get("file")
        if (
            _nonempty(statement_file)
            and _project_pdf_page_count(project_root, statement_file) is None
        ):
            statement_missing.append(
                "file (when supplied, a readable project-relative PDF)"
            )
        statement_missing += [
            field
            for field in statement_fields
            if statement.get(field) is not True
        ]
    if statement_missing:
        findings.append(
            _error(
                "pesose_budget_subaward_pi_statement",
                f"{label} needs a PI statement signed by the proposing "
                "institution's business office and included in the Budget "
                "Justification, with: " + ", ".join(statement_missing) + ".",
            )
        )

    justification = item.get("subaward_budget_justification")
    justification_fields = (
        "follows_main_budget_format",
        "line_items_identified_by_letter_and_number",
    )
    if not isinstance(justification, dict):
        justification_missing = ["file", *justification_fields]
    else:
        justification_missing = []
        page_count = _project_pdf_page_count(
            project_root, justification.get("file")
        )
        if page_count is None:
            justification_missing.append(
                "file (readable project-relative PDF)"
            )
        elif page_count > 5:
            findings.append(
                _error(
                    "pesose_budget_subaward_budget_justification_page_limit",
                    f"{label}'s separate subaward Budget Justification is "
                    f"{page_count} pages; the limit is 5 pages.",
                )
            )
        justification_missing += [
            field
            for field in justification_fields
            if justification.get(field) is not True
        ]
    if justification_missing:
        findings.append(
            _error(
                "pesose_budget_subaward_budget_justification",
                f"{label}'s separate budget justification needs: "
                + ", ".join(justification_missing)
                + ".",
            )
        )
    if item.get("co_pi_listed_on_line_a") is not True:
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_budget_subaward_co_pi_line_a",
                message=(
                    f"Confirm that {label}'s co-PI is identified on subaward "
                    "Line A and set co_pi_listed_on_line_a: true. NSF says the "
                    "co-PI should be listed, so this remains manual review."
                ),
            )
        )

    travel = item.get("travel", [])
    if isinstance(travel, list):
        for index, trip in enumerate(travel):
            if not isinstance(trip, dict):
                continue
            missing = [
                field
                for field in ("description", "necessity")
                if not _nonempty(trip.get(field))
            ]
            if missing:
                findings.append(
                    _error(
                        "pesose_budget_subaward_travel_justification",
                        f"{label} subaward trip {index + 1} must provide: "
                        + ", ".join(missing)
                        + ".",
                    )
                )
    return findings


def _validate_consultant_statement(
    item: dict[str, Any], label: str, project_root: Path
) -> list[BudgetPreparationFinding]:
    statement = item.get("signed_statement")
    required = (
        "signed",
        "confirms_availability",
        "confirms_time_commitment",
        "confirms_role",
        "confirms_rate",
    )
    missing = []
    if not isinstance(statement, dict):
        missing = ["file", *required]
    else:
        if (
            _project_pdf_page_count(project_root, statement.get("file"))
            is None
        ):
            missing.append("file (readable project-relative PDF)")
        missing += [
            field for field in required if statement.get(field) is not True
        ]
    if not missing:
        return []
    return [
        _error(
            "pesose_budget_consultant_statement",
            f"{label} exceeds the consultant-statement threshold and needs "
            "a project-relative signed_statement with: "
            + ", ".join(missing)
            + ".",
        )
    ]


def _validate_ip_agreement(
    item: dict[str, Any], label: str, project_root: Path
) -> list[BudgetPreparationFinding]:
    agreement = item.get("ip_rights_agreement")
    if (
        isinstance(agreement, dict)
        and agreement.get("executed") is True
        and _project_pdf_page_count(project_root, agreement.get("file"))
        is not None
    ):
        return []
    return [
        _error(
            "pesose_budget_subaward_ip_agreement",
            f"{label} needs an executed, project-relative "
            "ip_rights_agreement file for Other Supplementary Documents.",
        )
    ]


def _validate_indirect_costs(
    data: dict[str, Any], rules: BudgetPreparationRules, years: int
) -> list[BudgetPreparationFinding]:
    indirect = data.get("indirect_costs", {})
    if not isinstance(indirect, dict):
        return []
    rate = _number(indirect.get("rate", 0))
    method = _normalize_token(indirect.get("method"))
    if not method:
        if rate is not None and rate > 0:
            return [
                _error(
                    "pesose_budget_indirect_method",
                    "A positive indirect-cost request must declare method: "
                    "nicra or de_minimis.",
                )
            ]
        return []

    if method == "none":
        if rate == 0:
            return []
        return [
            _error(
                "pesose_budget_indirect_method",
                "indirect_costs.method: none requires rate: 0.",
            )
        ]

    if method == "nicra":
        missing = []
        if indirect.get("has_current_nicra") is not True:
            missing.append("has_current_nicra: true")
        if indirect.get("uses_negotiated_rate") is not True:
            missing.append("uses_negotiated_rate: true")
        if rules.indirect_base_amount_verification_required:
            if _year_values(indirect.get("base_amount"), years) is None:
                missing.append("base_amount for every budget year")
            if indirect.get("base_amount_verified_against_nicra") is not True:
                missing.append("base_amount_verified_against_nicra: true")
        if not missing:
            return []
        return [
            _error(
                "pesose_budget_nicra_attestation",
                "The NICRA route requires explicit attestations: "
                + ", ".join(missing)
                + ".",
            )
        ]

    if method == "de_minimis":
        findings: list[BudgetPreparationFinding] = []
        if indirect.get("has_current_nicra") is not False:
            findings.append(
                _error(
                    "pesose_budget_de_minimis_nicra_attestation",
                    "The de minimis route must explicitly attest "
                    "has_current_nicra: false.",
                )
            )
        required_rate = rules.de_minimis_indirect_rate
        if required_rate is not None and (
            rate is None or not math.isclose(rate, required_rate)
        ):
            findings.append(
                _error(
                    "pesose_budget_de_minimis_rate",
                    f"The de minimis indirect-cost rate must be "
                    f"{required_rate:.0%}.",
                )
            )
        required_base = _normalize_token(rules.de_minimis_indirect_base)
        base = _normalize_token(indirect.get("base"))
        if required_base and base != required_base:
            findings.append(
                _error(
                    "pesose_budget_de_minimis_base",
                    "The de minimis indirect-cost base must be MTDC.",
                )
            )
        if rules.indirect_base_amount_verification_required:
            if _year_values(indirect.get("base_amount"), years) is None:
                findings.append(
                    _error(
                        "pesose_budget_indirect_base_amount",
                        "Provide indirect_costs.base_amount as a non-negative "
                        "amount for every budget year. GrantKit cannot infer "
                        "all MTDC exclusions from legacy budget categories.",
                    )
                )
            if indirect.get("base_amount_verified_as_mtdc") is not True:
                findings.append(
                    _error(
                        "pesose_budget_indirect_base_attestation",
                        "Attest indirect_costs.base_amount_verified_as_mtdc: "
                        "true after applying the current MTDC definition.",
                    )
                )
        return findings

    return [
        _error(
            "pesose_budget_indirect_method",
            "indirect_costs.method must be nicra, de_minimis, or none.",
        )
    ]


def _validate_icorps(
    data: dict[str, Any],
    rules: BudgetPreparationRules,
    years: int,
    *,
    required: bool,
    declared_amount: Optional[float],
) -> list[BudgetPreparationFinding]:
    """Validate mandatory I-Corps team and tagged actual-budget evidence."""
    findings: list[BudgetPreparationFinding] = []
    tagged = []
    seen_ids: set[str] = set()
    allowed = {
        _normalize_token(value) for value in rules.icorps_allowed_cost_types
    }
    prohibited = {
        _normalize_token(value) for value in rules.icorps_prohibited_cost_types
    }
    salary_cap_roles = {
        _normalize_token(value)
        for value in rules.icorps_current_salary_cap_roles
    }
    salary_support_amount = 0.0
    salary_role_by_cost_type = {
        "technical_lead_salary": "technical_lead",
        "entrepreneurial_lead_salary": "entrepreneurial_lead",
    }

    for context, item in _iter_icorps_budget_items(data):
        amount = _number(item.get("icorps_amount"))
        if amount is None or amount <= 0:
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            findings.append(
                _error(
                    "pesose_icorps_budget_item_id",
                    f"{context} with icorps_amount must have a non-empty id.",
                )
            )
            item_id = f"<missing:{context}>"
        elif item_id in seen_ids:
            findings.append(
                _error(
                    "pesose_icorps_budget_item_id",
                    f"I-Corps budget item id '{item_id}' is duplicated.",
                )
            )
        else:
            seen_ids.add(item_id)

        total = _line_total(item, years)
        if amount > total and not math.isclose(amount, total, abs_tol=1):
            findings.append(
                _error(
                    "pesose_icorps_budget_item_amount",
                    f"{context} assigns USD {amount:,.0f} to I-Corps but the "
                    f"actual budget line totals only USD {total:,.0f}.",
                )
            )

        cost_type = _normalize_token(item.get("icorps_cost_type"))
        if not cost_type:
            findings.append(
                _error(
                    "pesose_icorps_cost_type_missing",
                    f"{context} must declare icorps_cost_type.",
                )
            )
        elif cost_type in prohibited:
            findings.append(
                _error(
                    "pesose_icorps_cost_prohibited",
                    f"{context} uses prohibited I-Corps cost type "
                    f"'{cost_type}'.",
                )
            )
        elif allowed and cost_type not in allowed:
            findings.append(
                BudgetPreparationFinding(
                    level="warning",
                    rule="pesose_icorps_cost_manual_review",
                    message=(
                        f"{context} uses I-Corps cost type '{cost_type}', which "
                        "is neither an example component nor an explicit "
                        "prohibition in the NSF update. Confirm allowability."
                    ),
                )
            )

        if rules.icorps_domestic_travel_only and (
            context.startswith("foreign travel")
            or cost_type == "international_travel"
        ):
            findings.append(
                _error(
                    "pesose_icorps_international_travel_prohibited",
                    f"{context} assigns international travel to I-Corps; only "
                    "U.S. travel is allowed.",
                )
            )

        role = _normalize_token(item.get("icorps_role"))
        salary_role = salary_role_by_cost_type.get(cost_type)
        is_line_ab_personnel = context.startswith(
            ("Line A person ", "Line B person ")
        )
        if salary_role and not is_line_ab_personnel:
            findings.append(
                _error(
                    "pesose_icorps_salary_cost_context",
                    f"{context} uses I-Corps salary cost type '{cost_type}', "
                    "but TL/EL salary support must be assigned to a Line A or "
                    "Line B personnel entry. This amount does not count as "
                    "I-Corps salary support.",
                )
            )
        elif salary_role:
            if role and role != salary_role:
                findings.append(
                    _error(
                        "pesose_icorps_salary_role_mismatch",
                        f"{context} declares icorps_role '{role}', which does "
                        f"not match salary cost type '{cost_type}'.",
                    )
                )
            role = salary_role
            salary_support_amount += amount
        if salary_role in salary_cap_roles and is_line_ab_personnel:
            current = _number(item.get("current_salary_rate"))
            icorps_rate = _number(
                item.get(
                    "icorps_salary_rate",
                    item.get("requested_salary_rate", item.get("base_salary")),
                )
            )
            attested = (
                item.get("icorps_salary_rate_no_greater_than_current") is True
            )
            numeric_violation = (
                current is not None
                and icorps_rate is not None
                and icorps_rate > current
            )
            if not attested or numeric_violation:
                findings.append(
                    _error(
                        "pesose_icorps_salary_rate",
                        f"{context} must show that the {role} I-Corps salary "
                        "rate does not exceed the current salary rate.",
                    )
                )
        tagged.append((str(item_id), role, amount))

    actual_amount = sum(amount for _, _, amount in tagged)
    cap = rules.icorps_budget_cap
    if cap is not None and actual_amount > cap:
        findings.append(
            _error(
                "pesose_icorps_actual_budget_over_cap",
                f"Actual tagged I-Corps costs are USD {actual_amount:,.0f}; "
                f"the maximum is USD {cap:,.0f}.",
            )
        )
    declared = _number(declared_amount)
    if declared is not None and not math.isclose(
        declared, actual_amount, abs_tol=1
    ):
        findings.append(
            _error(
                "pesose_icorps_budget_link_mismatch",
                f"pesose.icorps_budget_amount is USD {declared:,.0f}, but "
                f"actual tagged budget lines total USD {actual_amount:,.0f}.",
            )
        )

    if not required:
        return findings
    if actual_amount <= 0:
        findings.append(
            _warning(
                "pesose_icorps_actual_budget_missing",
                "I-Corps is not waived, but no actual budget line has a "
                "positive icorps_amount. NSF sets a maximum rather than a "
                "positive minimum; confirm that required participation can "
                "be completed without requested costs.",
            )
        )
    if salary_support_amount <= 0:
        findings.append(
            _warning(
                "pesose_icorps_salary_support_missing",
                "I-Corps is not waived, but no positive tagged TL/EL salary "
                "support is present. NSF says the budget should include "
                "salary support for the TL and EL; review this manually.",
            )
        )
    if data.get("icorps_salary_support_is_sufficient") is not True:
        findings.append(
            _warning(
                "pesose_icorps_salary_support_attestation",
                "I-Corps is not waived; review and attest "
                "icorps_salary_support_is_sufficient: true after confirming "
                "whether the budget provides the TL/EL salary support NSF "
                "recommends for the mandatory experiential activities.",
            )
        )
    if (
        actual_amount > 0
        and data.get("icorps_budget_justification_includes_tagged_costs")
        is not True
    ):
        findings.append(
            _error(
                "pesose_icorps_budget_justification_attestation",
                "Attest icorps_budget_justification_includes_tagged_costs: "
                "true so actual budget tags are tied to the justification.",
            )
        )

    team = data.get("icorps_team")
    if not isinstance(team, list):
        team = []
    team_roles: set[str] = set()
    for index, member in enumerate(team):
        if not isinstance(member, dict):
            continue
        if not _nonempty(member.get("name")):
            findings.append(
                BudgetPreparationFinding(
                    level="warning",
                    rule="pesose_icorps_team_member_name_manual_review",
                    message=(
                        f"I-Corps planning entry {index + 1} does not name the "
                        "designated individual. Confirm the post-award roster."
                    ),
                )
            )
        role = _normalize_token(member.get("role"))
        if role:
            team_roles.add(role)
        if (
            rules.icorps_team_agreement_required
            and member.get("agreed_to_program_requirements") is not True
        ):
            findings.append(
                BudgetPreparationFinding(
                    level="warning",
                    rule="pesose_icorps_team_agreement_manual_review",
                    message=(
                        f"I-Corps planning entry {index + 1} has not attested "
                        "agreed_to_program_requirements: true. Confirm this "
                        "with the post-award training team."
                    ),
                )
            )

    required_roles = {
        _normalize_token(value) for value in rules.icorps_required_team_roles
    }
    missing_roles = sorted(required_roles - team_roles)
    if missing_roles:
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_icorps_team_roles_manual_review",
                message=(
                    "The proposed I-Corps planning roster is missing post-award "
                    "roles: "
                    + ", ".join(missing_roles)
                    + ". Confirm the eventual training roster."
                ),
            )
        )

    expected_format = _normalize_token(rules.icorps_training_format)
    acknowledged_format = _normalize_token(
        data.get("icorps_training_format_acknowledged")
    )
    if expected_format and acknowledged_format != expected_format:
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_icorps_training_format_manual_review",
                message=(
                    f"Confirm the current I-Corps training format and declare "
                    f"icorps_training_format_acknowledged: {expected_format}."
                ),
            )
        )
    team_size_max = rules.icorps_team_size_manual_review_max
    if team_size_max is not None and len(team) > team_size_max:
        findings.append(
            BudgetPreparationFinding(
                level="warning",
                rule="pesose_icorps_team_size_manual_review",
                message=(
                    f"The current update expects at most {team_size_max} "
                    "training-team members, while the March guidance permits "
                    "co-TL/co-EL participation. Confirm the roster with NSF."
                ),
            )
        )

    return findings


def _iter_personnel(
    data: dict[str, Any],
) -> Iterator[tuple[str, int, dict[str, Any]]]:
    personnel = data.get("personnel", {})
    if not isinstance(personnel, dict):
        return
    for line, key in (("A", "senior_key"), ("B", "other")):
        entries = personnel.get(key, [])
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if isinstance(entry, dict):
                yield line, index, entry


def _iter_trips(
    data: dict[str, Any],
) -> Iterator[tuple[str, int, dict[str, Any]]]:
    travel = data.get("travel", {})
    if not isinstance(travel, dict):
        return
    for kind in ("domestic", "foreign"):
        entries = travel.get(kind, [])
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if isinstance(entry, dict):
                yield kind, index, entry


def _iter_icorps_budget_items(
    data: dict[str, Any],
) -> Iterator[tuple[str, dict[str, Any]]]:
    for line, index, person in _iter_personnel(data):
        yield f"Line {line} person {index + 1}", person

    fringe = data.get("fringe_benefits")
    if isinstance(fringe, dict):
        yield "fringe benefits", fringe

    equipment = data.get("equipment", [])
    if isinstance(equipment, list):
        for index, item in enumerate(equipment):
            if isinstance(item, dict):
                yield f"equipment item {index + 1}", item

    for kind, index, trip in _iter_trips(data):
        yield f"{kind} travel item {index + 1}", trip

    participant = data.get("participant_support", [])
    if isinstance(participant, list):
        for index, item in enumerate(participant):
            if isinstance(item, dict):
                yield f"participant-support item {index + 1}", item

    for index, item in enumerate(_other_direct_costs(data)):
        yield f"other-direct-cost item {index + 1}", item


def _other_direct_costs(data: dict[str, Any]) -> list[dict[str, Any]]:
    entries = data.get("other_direct_costs", [])
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _payment_channel(item: dict[str, Any]) -> Optional[str]:
    category = _normalize_token(item.get("category"))
    if "subaward" in category.replace("_", ""):
        return "subaward"
    if "consultant" in category:
        return "consultant"
    if "contractor" in category or "subcontract" in category:
        return "contractor"
    return None


def _is_materials_item(item: dict[str, Any]) -> bool:
    category = _normalize_token(item.get("category"))
    return "material" in category and "suppl" in category


def _is_line_g_services_item(
    item: dict[str, Any], channel: Optional[str]
) -> bool:
    category = _normalize_token(item.get("category"))
    return (
        channel == "contractor"
        or "fee_for_service" in category
        or category
        in {
            "other",
            "other_costs",
            "other_direct_costs",
        }
    )


def _budget_years(data: dict[str, Any]) -> int:
    years = data.get("years_in_budget", 1)
    if isinstance(years, int) and not isinstance(years, bool) and years > 0:
        return years
    return 1


def _validate_nonnegative_budget_amounts(
    data: dict[str, Any],
) -> list[BudgetPreparationFinding]:
    """Reject signed values that could reduce the calculator's funder total."""
    items: list[tuple[str, dict[str, Any]]] = list(
        _iter_icorps_budget_items(data)
    )
    indirect = data.get("indirect_costs")
    if isinstance(indirect, dict):
        items.append(("indirect costs", indirect))

    fixed_keys = {
        "amount",
        "base_salary",
        "bls_percentile_rate",
        "consultant_rate",
        "current_salary_rate",
        "equipment_amount",
        "funding_amount",
        "funds_per_year",
        "icorps_amount",
        "icorps_salary_rate",
        "rate",
        "requested_funding_amount",
        "requested_salary_rate",
        "total",
        "total_requested",
        "total_requested_salary",
    }
    invalid_paths = []
    for context, item in items:
        for key, value in item.items():
            if key not in fixed_keys and not re.fullmatch(r"year_\d+", key):
                continue
            number = _number(value)
            if number is None or number < 0:
                invalid_paths.append(f"{context}.{key}")
        if context == "indirect costs":
            base_amount = item.get("base_amount")
            if isinstance(base_amount, dict):
                for key, value in base_amount.items():
                    number = _number(value)
                    if number is None or number < 0:
                        invalid_paths.append(
                            f"indirect costs.base_amount.{key}"
                        )
    if not invalid_paths:
        return []
    return [
        _error(
            "pesose_budget_amount_nonnegative",
            "Budget amounts and rates must be finite and non-negative; fix: "
            + ", ".join(invalid_paths)
            + ".",
        )
    ]


def _validate_budget_period(
    data: dict[str, Any], rules: BudgetPreparationRules
) -> list[BudgetPreparationFinding]:
    value = data.get("years_in_budget", 1)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        return [
            _error(
                "pesose_budget_years_invalid",
                "years_in_budget must be a positive integer.",
            )
        ]
    maximum = rules.max_budget_years
    if maximum is not None and value > maximum:
        return [
            _error(
                "pesose_budget_years_exceeded",
                f"PESOSE Track 2 budget.yaml covers {value} years; the "
                f"maximum project period is {maximum} years.",
            )
        ]
    return []


def _validate_budget_year_allocations(
    data: dict[str, Any], years: int
) -> list[BudgetPreparationFinding]:
    """Ensure each funded line participates in legacy calculator totals."""
    missing = []
    mismatched = []
    for context, item in _iter_icorps_budget_items(data):
        if _line_total(item, years) <= 0:
            continue
        if (
            context == "fringe benefits"
            and _number(item.get("rate")) is not None
        ):
            # The calculator can derive fringe from its rate and salary lines.
            continue
        has_year_amount = any(
            _number(item.get(f"year_{year}")) is not None
            for year in range(1, years + 1)
        )
        if not has_year_amount and _number(item.get("funds_per_year")) is None:
            missing.append(context)
            continue
        allocated = _budgeted_line_total(item, years)
        declared = next(
            (
                number
                for key in ("funding_amount", "total", "amount")
                if (number := _number(item.get(key))) is not None
            ),
            None,
        )
        if (
            declared is not None
            and allocated is not None
            and not math.isclose(declared, allocated, abs_tol=1)
        ):
            mismatched.append(context)
    findings = []
    if missing:
        findings.append(
            _error(
                "pesose_budget_year_allocation_missing",
                "Funded lines must provide year_N amounts or funds_per_year so "
                "they participate in GrantKit's total and cap arithmetic; fix: "
                + ", ".join(missing)
                + ".",
            )
        )
    if mismatched:
        findings.append(
            _error(
                "pesose_budget_line_total_mismatch",
                "Declared line totals must match their year allocation; fix: "
                + ", ".join(mismatched)
                + ".",
            )
        )
    return findings


def _mapping_has_funding(item: dict[str, Any], years: int) -> bool:
    if _line_total(item, years) > 0:
        return True
    rate = _number(item.get("rate"))
    return rate is not None and rate > 0


def _line_total(item: dict[str, Any], years: int) -> float:
    yearly = [
        _number(item.get(f"year_{year}")) for year in range(1, years + 1)
    ]
    if any(value is not None for value in yearly):
        return sum(max(0.0, value or 0.0) for value in yearly)
    per_year = _number(item.get("funds_per_year"))
    if per_year is not None:
        return max(0.0, per_year) * years
    for key in ("total_requested", "total", "funding_amount"):
        value = _number(item.get(key))
        if value is not None:
            return max(0.0, value)
    amount = _number(item.get("amount"))
    return max(0.0, amount or 0.0)


def _budgeted_line_total(item: dict[str, Any], years: int) -> Optional[float]:
    yearly = [
        _number(item.get(f"year_{year}")) for year in range(1, years + 1)
    ]
    if any(value is not None for value in yearly):
        return sum(max(0.0, value or 0.0) for value in yearly)
    per_year = _number(item.get("funds_per_year"))
    if per_year is not None:
        return max(0.0, per_year) * years
    for key in ("funding_amount", "amount", "total"):
        value = _number(item.get(key))
        if value is not None:
            return max(0.0, value)
    return None


def _year_values(value: Any, years: int) -> Optional[list[float]]:
    if not isinstance(value, dict):
        return None
    expected = [f"year_{year}" for year in range(1, years + 1)]
    values = [_number(value.get(key)) for key in expected]
    if any(number is None or number < 0 for number in values):
        return None
    return [float(number) for number in values if number is not None]


def _month_values(value: Any, years: int) -> Optional[list[float]]:
    number = _number(value)
    if number is not None:
        if number < 0 or years != 1:
            return None
        return [number]
    return _year_values(value, years)


def _person_label(person: dict[str, Any], line: str, index: int) -> str:
    for key in ("name", "title", "role", "category"):
        if _nonempty(person.get(key)):
            return str(person[key])
    return f"Line {line} person {index + 1}"


def _is_bls_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and (
        host == "bls.gov" or host.endswith(".bls.gov")
    )


def _has_markdown_table(text: str) -> bool:
    delimiter = re.compile(
        r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
    )
    lines = text.splitlines()
    return any(
        "|" in lines[index - 1] and delimiter.match(line)
        for index, line in enumerate(lines[1:], start=1)
    )


def _project_file(root: Path, value: Any) -> Optional[Path]:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _project_pdf_page_count(root: Path, value: Any) -> Optional[int]:
    path = _project_file(root, value)
    if path is None or path.suffix.casefold() != ".pdf":
        return None
    try:
        from pypdf import PdfReader

        page_count = len(PdfReader(path).pages)
    except Exception:
        return None
    return page_count if page_count > 0 else None


def _declares_equipment(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return math.isfinite(value) and value > 0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _number(value: Any) -> Optional[float]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    if isinstance(value, bool):
        return value
    return True


def _normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    token = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    aliases = {
        "non_profit": "nonprofit",
        "forprofit": "for_profit",
        "institution_of_higher_education": "higher_education",
    }
    return aliases.get(token, token)


def _error(rule: str, message: str) -> BudgetPreparationFinding:
    return BudgetPreparationFinding(level="error", rule=rule, message=message)


def _warning(rule: str, message: str) -> BudgetPreparationFinding:
    return BudgetPreparationFinding(
        level="warning", rule=rule, message=message
    )

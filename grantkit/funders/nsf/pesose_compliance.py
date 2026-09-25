"""Pure structural compliance checks for NSF PESOSE Track 2.

The validator accepts plain mappings, sequences, and Markdown strings. It
does not read :class:`~grantkit.core.project.GrantProject`, inspect the file
system, or infer substantive proposal coverage from keyword matches.

Rule sources:

* NSF 26-506 section IV and section V.A (eligibility, collaboration structure,
  letters, personnel table, and proposal content), including the IHE foreign-
  academic and international-branch exceptions and the PAPPG I.E.2 route for
  federal agencies and FFRDCs:
  https://www.nsf.gov/funding/opportunities/pesose-pathways-enable-secure-open-source-ecosystems/nsf26-506/solicitation
* NSF 26-506 section VI.A (Track 2 activity/review areas).
* NSF 26-506 section VII.B (TIP person-or-entity-of-concern special award
  condition; GrantKit requires manual review and does not cache dynamic lists).
* PAPPG 24-1 Supplement 2 and NSF ENG's July 2026 guidance (Research.gov DMSP
  fields, publication-supporting data availability, exceptions, and the
  justified no-product route):
  https://www.nsf.gov/policies/document/pappg24-1-supplement-2
  https://www.nsf.gov/eng/data-management-sharing-plans
* PAPPG 24-1 II.D.2.d/h/i and Supplement 1 (senior/key documents, Results
  from Prior NSF Support, the unified Mentoring Plan, the IHE Confucius-
  Institute restriction, covered-foreign unmanned-aircraft costs, and targeted
  research-security certifications):
  https://www.nsf.gov/policies/pappg/24-1/ch-2-proposal-preparation
  https://www.nsf.gov/policies/document/pappg24-1-supplement-1
  https://www.nsf.gov/notices/important/important-notice-no-149-updates-nsf-research-security/in149
* PAPPG 24-1 I.G.2 (valid and active UEI and SAM registration):
  https://www.nsf.gov/policies/pappg/24-1/ch-1-pre-submission

Declarations use the literal ``"not_applicable"`` only for a condition that
the accompanying scope declaration establishes does not apply. Missing,
false, or inapplicable required attestations remain errors.
"""

from __future__ import annotations

import math
import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final

NOT_APPLICABLE: Final = "not_applicable"

PESOSE_RULE_SOURCES: Final = {
    "eligibility": (
        "NSF 26-506 IV and V.A, Proposal Preparation Instructions; PAPPG "
        "24-1 I.G.2 for UEI and SAM registration; PAPPG 24-1 I.E.2 for "
        "federal agencies and FFRDCs"
    ),
    "letters": "NSF 26-506 V.A, Other Supplementary Documents item 1",
    "personnel": "NSF 26-506 V.A, Other Supplementary Documents item 2",
    "proposal_content": "NSF 26-506 V.A, Project Description",
    "track_2_activities": (
        "NSF 26-506 II, Measures of Success, and V.A and VI.A, Track 2"
    ),
    "award_conditions": (
        "NSF 26-506 VII.B, Special Award Conditions, CHIPS and Science Act "
        "section 10636 person-or-entity-of-concern prohibition"
    ),
    "dmsp": (
        "PAPPG 24-1 Supplement 2, II.D.2(i)(ii), and NSF ENG DMSP "
        "guidance updated July 2026"
    ),
    "senior_key_documents": "PAPPG 24-1 II.D.2.h",
    "prior_nsf_support": "PAPPG 24-1 II.D.2.d(iii)",
    "mentoring_plan": "PAPPG 24-1 II.D.2.i(i)",
    "supplement_1": (
        "PAPPG 24-1 Supplement 1 sections 3, 4, and 12 (NSF 26-200); "
        "NSF Important Notice 149 sections 1 and 2"
    ),
}

ALLOWED_ORGANIZATION_TYPES: Final = (
    "institution_of_higher_education",
    "nonprofit_nonacademic",
    "for_profit",
    "state_or_local_government",
    "tribal_nation",
    "federal_agency_or_ffrdc",
)

FEDERAL_FFRDC_EXCEPTION_ROUTES: Final = (
    "special_projects",
    "national_and_international_programs",
    "international_travel_awards",
)

PERSONNEL_COLUMNS: Final = (
    "Full name",
    "Organization(s)",
    "Role in the project",
)

DMSP_FIELDS: Final = (
    "Data or research product category",
    "Access policies and limitations",
    "Data standards and metadata",
    "Data or research product provenance",
    "Public archiving",
    "Timeline for public accessibility",
    "Data availability",
    "Accountability",
)

SENIOR_KEY_DOCUMENT_FIELDS: Final = (
    "biographical_sketch_file",
    "current_and_pending_support_file",
    "collaborators_and_other_affiliations_file",
    "synergistic_activities_file",
)

PRIOR_SUPPORT_REVIEW_ATTESTATIONS: Final = (
    "award_number_amount_and_period_addressed",
    "project_title_addressed",
    "results_under_intellectual_merit_and_broader_impacts_addressed",
    "publications_or_no_publications_statement_addressed",
    "research_products_and_availability_addressed",
    "renewal_relationship_addressed",
)

ALL_PROPOSAL_ATTESTATIONS: Final = {
    "existing_public_product_pointer": (
        "the proposal points to the existing publicly available open-source "
        "product through an inline citation and References Cited entry"
    ),
    "current_product_status": (
        "the proposal covers the current development/testing model, "
        "dissemination methods, user base, and contributor base"
    ),
    "problem_being_addressed": (
        "the proposal describes the problem being addressed"
    ),
    "team_qualifications": (
        "the proposal strongly justifies that the team is qualified"
    ),
}

TRACK_2_ACTIVITY_ATTESTATIONS: Final = {
    "track2_ecosystem_growth": "Ecosystem Growth",
    "track2_organization_and_governance": "Organization and Governance",
    "track2_continuous_development": "Continuous Development",
    "track2_risk_analysis_and_security": "Risk Analysis and Security",
    "track2_community_building": "Community Building",
    "track2_sustainability": "Sustainability",
    "track2_evaluation_plan": "Evaluation Plan",
    "track2_measure_of_success": (
        "at least one NSF 26-506 Measure of Success"
    ),
}

_ORGANIZATION_TYPE_ALIASES: Final = {
    "ihe": "institution_of_higher_education",
    "higher_education": "institution_of_higher_education",
    "institution_of_higher_education": "institution_of_higher_education",
    "institution_higher_education": "institution_of_higher_education",
    "nonprofit": "nonprofit_nonacademic",
    "non_profit": "nonprofit_nonacademic",
    "nonprofit_nonacademic": "nonprofit_nonacademic",
    "non_profit_non_academic": "nonprofit_nonacademic",
    "nonprofit_nonacademic_organization": "nonprofit_nonacademic",
    "non_profit_non_academic_organization": "nonprofit_nonacademic",
    "for_profit": "for_profit",
    "for_profit_organization": "for_profit",
    "state_local": "state_or_local_government",
    "state_or_local": "state_or_local_government",
    "state_or_local_government": "state_or_local_government",
    "state_government": "state_or_local_government",
    "local_government": "state_or_local_government",
    "tribal_nation": "tribal_nation",
    "federal_agency": "federal_agency_or_ffrdc",
    "other_federal_agency": "federal_agency_or_ffrdc",
    "ffrdc": "federal_agency_or_ffrdc",
    "federal_agency_or_ffrdc": "federal_agency_or_ffrdc",
}

_PLACEHOLDER_RE: Final = re.compile(
    r"(?:\b(?:todo|tbd|placeholder|lorem\s+ipsum)\b|"
    r"\[\s*(?:to\s+be\s+completed|insert|add|your)\b[^]]*\])",
    re.IGNORECASE,
)
_SEPARATOR_CELL_RE: Final = re.compile(r"^:?-{3,}:?$")
_PRODUCT_HEADING_RE: Final = re.compile(
    r"^\s*#{2,6}\s+(?:data\s+or\s+research\s+)?product"
    r"(?:\s+\d+(?:\s*[:\-\u2014].*)?|\s*:\s*.+?)\s*#*\s*$",
    re.IGNORECASE,
)
_HEADING_RE: Final = re.compile(r"^\s*#{3,6}\s+(?P<label>.+?)\s*#*\s*$")
_BOLD_FIELD_RE: Final = re.compile(
    r"^\s*(?:[-+*]\s+)?\*\*(?P<label>.+?)\*\*\s*:?[ \t]*" r"(?P<value>.*)$"
)
_BULLET_FIELD_RE: Final = re.compile(
    r"^\s*[-+*]\s+(?P<label>[^:]+):\s*(?P<value>.*)$"
)


@dataclass(frozen=True, slots=True)
class PESOSEFinding:
    """One pure validation finding, suitable for later adapter layers."""

    level: str
    rule: str
    message: str


@dataclass(slots=True)
class _DMSPProduct:
    label: str
    fields: dict[str, list[list[str]]] = field(default_factory=dict)
    unknown_fields: list[str] = field(default_factory=list)
    has_unstructured_content: bool = False


def validate_pesose_compliance(
    *,
    proposal_submission_date: str | None = None,
    eligibility: Mapping[str, object] | None = None,
    letter_manifest: Mapping[str, Mapping[str, object]] | None = None,
    actual_letter_files: Sequence[str] | None = None,
    actual_letter_page_counts: Mapping[str, int] | None = None,
    facilities_continuation: Mapping[str, object] | None = None,
    personnel_markdown: str | None = None,
    declared_roster: Sequence[object] | None = None,
    personnel_declarations: Mapping[str, object] | None = None,
    senior_key_document_manifest: (
        Mapping[str, Mapping[str, object]] | None
    ) = None,
    declared_senior_key_people: Sequence[object] | None = None,
    actual_senior_key_document_files: Sequence[str] | None = None,
    actual_synergistic_activities_page_counts: Mapping[str, int] | None = None,
    prior_nsf_support_declarations: Mapping[str, object] | None = None,
    mentoring_plan_declarations: Mapping[str, object] | None = None,
    mentoring_plan_evidence: Mapping[str, object] | None = None,
    supplement_1_declarations: Mapping[str, object] | None = None,
    dmsp_markdown: str | None = None,
    dmsp_declarations: Mapping[str, object] | None = None,
    manual_review_attestations: Mapping[str, object] | None = None,
    award_condition_attestations: Mapping[str, object] | None = None,
) -> list[PESOSEFinding]:
    """Validate supplied PESOSE compliance evidence without performing I/O."""
    findings: list[PESOSEFinding] = []
    findings += validate_eligibility(eligibility)
    findings += validate_letter_manifest(
        letter_manifest,
        facilities_continuation,
        actual_letter_files,
        actual_letter_page_counts,
    )
    if actual_letter_files is None:
        findings.append(
            _error(
                "pesose_letters_file_inventory_required",
                "The full PESOSE validation requires the actual letter-file "
                "inventory so it can be reconciled to the manifest.",
            )
        )
    if actual_letter_page_counts is None:
        findings.append(
            _error(
                "pesose_letters_actual_page_counts_required",
                "The full PESOSE validation requires adapter-supplied actual "
                "letter PDF page counts for reconciliation.",
            )
        )
    findings += validate_personnel_table(personnel_markdown, declared_roster)
    findings += _validate_full_personnel_evidence(
        letter_manifest, declared_roster, personnel_declarations
    )
    findings += validate_senior_key_personnel_reconciliation(
        personnel_markdown,
        declared_roster,
        declared_senior_key_people,
        senior_key_document_manifest,
    )
    findings += validate_senior_key_document_manifest(
        senior_key_document_manifest,
        declared_senior_key_people,
        actual_senior_key_document_files,
        actual_synergistic_activities_page_counts,
        proposal_submission_date,
    )
    if declared_senior_key_people is None:
        findings.append(
            _error(
                "pesose_senior_key_declared_roster_required",
                "The full PESOSE validation requires the declared Senior/Key "
                "roster so every person's documents can be reconciled.",
            )
        )
    if actual_senior_key_document_files is None:
        findings.append(
            _error(
                "pesose_senior_key_file_inventory_required",
                "The full PESOSE validation requires the actual Senior/Key "
                "document-file inventory for reconciliation.",
            )
        )
    if actual_synergistic_activities_page_counts is None:
        findings.append(
            _error(
                "pesose_senior_key_actual_page_counts_required",
                "The full PESOSE validation requires adapter-supplied actual "
                "Synergistic Activities PDF page counts.",
            )
        )
    findings += validate_prior_nsf_support(prior_nsf_support_declarations)
    findings += validate_mentoring_plan(
        mentoring_plan_declarations, mentoring_plan_evidence
    )
    if mentoring_plan_evidence is None:
        findings.append(
            _error(
                "pesose_mentoring_plan_evidence_required",
                "The full PESOSE validation requires passed Mentoring Plan "
                "file/page evidence for reconciliation.",
            )
        )
    organization_type = (
        eligibility.get("organization_type")
        if isinstance(eligibility, Mapping)
        else None
    )
    findings += validate_supplement_1(
        supplement_1_declarations, organization_type=organization_type
    )
    findings += validate_dmsp(dmsp_markdown, dmsp_declarations)
    findings += validate_manual_review_attestations(manual_review_attestations)
    findings += validate_tip_award_conditions(award_condition_attestations)
    return findings


def validate_eligibility(
    declarations: Mapping[str, object] | None,
) -> list[PESOSEFinding]:
    """Validate explicit NSF 26-506 IV/V.A eligibility declarations."""
    if not isinstance(declarations, Mapping):
        return [
            _error(
                "pesose_eligibility_declarations",
                "PESOSE eligibility declarations must be a mapping.",
            )
        ]

    findings: list[PESOSEFinding] = []
    organization_type = _canonical_organization_type(
        declarations.get("organization_type")
    )
    if organization_type is None:
        allowed = ", ".join(ALLOWED_ORGANIZATION_TYPES)
        findings.append(
            _error(
                "pesose_eligibility_organization_type",
                "organization_type must explicitly identify an allowed NSF "
                f"26-506 proposing organization type: {allowed}.",
            )
        )

    _require_true(
        declarations,
        "uei_is_valid_and_active",
        findings,
        "pesose_eligibility_active_uei",
        "The proposing organization must explicitly attest "
        "uei_is_valid_and_active: true.",
    )
    _require_true(
        declarations,
        "sam_registration_is_valid_and_active",
        findings,
        "pesose_eligibility_active_sam_registration",
        "The proposing organization must explicitly attest "
        "sam_registration_is_valid_and_active: true.",
    )
    _require_true(
        declarations,
        "single_lead_organization",
        findings,
        "pesose_eligibility_single_lead",
        "A PESOSE proposal must explicitly attest that one organization is "
        "the single lead.",
    )

    has_other_nsf_funded_organizations = _require_boolean(
        declarations,
        "has_other_nsf_funded_organizations",
        findings,
        "pesose_eligibility_collaboration_scope",
        "Declare has_other_nsf_funded_organizations as true or false so the "
        "mandatory lead/subaward structure can be evaluated.",
    )
    if has_other_nsf_funded_organizations is not None:
        _require_conditional(
            declarations,
            "all_other_nsf_funded_organizations_are_subawardees",
            applicable=has_other_nsf_funded_organizations,
            findings=findings,
            rule="pesose_eligibility_subaward_structure",
            required_message=(
                "Every NSF-funded organization other than the single lead "
                "must explicitly be declared a subawardee."
            ),
            inapplicable_message=(
                "all_other_nsf_funded_organizations_are_subawardees must be "
                "not_applicable when no other organization receives NSF "
                "funding."
            ),
        )
        _require_conditional(
            declarations,
            "all_subawardees_eligible",
            applicable=has_other_nsf_funded_organizations,
            findings=findings,
            rule="pesose_eligibility_subawardees",
            required_message=(
                "Every subawardee must explicitly be eligible to submit "
                "under NSF 26-506."
            ),
            inapplicable_message=(
                "all_subawardees_eligible must be not_applicable when there "
                "are no subawardees."
            ),
        )

    has_non_nsf_supported_team_organizations = _require_boolean(
        declarations,
        "has_non_nsf_supported_team_organizations",
        findings,
        "pesose_eligibility_non_nsf_participant_scope",
        "Declare has_non_nsf_supported_team_organizations as true or false "
        "so unfunded team participation can be evaluated separately from "
        "subawards.",
    )
    if has_non_nsf_supported_team_organizations is not None:
        _require_conditional(
            declarations,
            "all_non_nsf_supported_team_organizations_receive_no_nsf_support",
            applicable=has_non_nsf_supported_team_organizations,
            findings=findings,
            rule="pesose_eligibility_non_nsf_participants",
            required_message=(
                "Every organization using the non-NSF-supported team route, "
                "including an otherwise ineligible organization, must "
                "explicitly receive no NSF support."
            ),
            inapplicable_message=(
                "all_non_nsf_supported_team_organizations_receive_no_nsf_"
                "support must be not_applicable when there are no such team "
                "organizations."
            ),
        )

    if organization_type is not None:
        ownership_applies = organization_type in {
            "nonprofit_nonacademic",
            "for_profit",
        }
        _require_conditional(
            declarations,
            "us_based_owned_and_controlled",
            applicable=ownership_applies,
            findings=findings,
            rule="pesose_eligibility_us_ownership_control",
            required_message=(
                "A nonprofit or for-profit proposer must explicitly attest "
                "that it is U.S.-based, U.S.-owned, and U.S.-controlled."
            ),
            inapplicable_message=(
                "us_based_owned_and_controlled must be not_applicable for "
                "this organization type."
            ),
        )

        is_nonprofit = organization_type == "nonprofit_nonacademic"
        _require_conditional(
            declarations,
            "nonprofit_directly_associated_with_education_or_research",
            applicable=is_nonprofit,
            findings=findings,
            rule="pesose_eligibility_nonprofit_activity",
            required_message=(
                "A nonprofit nonacademic proposer must explicitly attest that "
                "it is directly associated with educational or research "
                "activities."
            ),
            inapplicable_message=(
                "nonprofit_directly_associated_with_education_or_research "
                "must be not_applicable for this organization type."
            ),
        )

        _require_conditional(
            declarations,
            "for_profit_has_strong_scientific_or_engineering_capabilities",
            applicable=organization_type == "for_profit",
            findings=findings,
            rule="pesose_eligibility_for_profit_capabilities",
            required_message=(
                "A for-profit proposer must be manually attested to have "
                "strong scientific or engineering research or education "
                "capabilities."
            ),
            inapplicable_message=(
                "for_profit_has_strong_scientific_or_engineering_capabilities "
                "must be not_applicable for this organization type."
            ),
        )

        is_ihe = organization_type == "institution_of_higher_education"
        _require_conditional(
            declarations,
            "ihe_is_accredited",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_eligibility_ihe_accreditation",
            required_message=(
                "An IHE proposer must explicitly attest that it is accredited."
            ),
            inapplicable_message=(
                "ihe_is_accredited must be not_applicable for a non-IHE "
                "proposer."
            ),
        )
        _require_conditional(
            declarations,
            "ihe_has_us_campus",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_eligibility_ihe_us_campus",
            required_message=(
                "An IHE proposer must explicitly attest that it has a campus "
                "located in the United States."
            ),
            inapplicable_message=(
                "ihe_has_us_campus must be not_applicable for a non-IHE "
                "proposer."
            ),
        )
        _require_conditional(
            declarations,
            "all_non_exception_senior_key_have_eligible_ihe_appointments",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_eligibility_ihe_appointments",
            required_message=(
                "An IHE proposer must attest that every PI, co-PI, and other "
                "Senior/Key person using the proposing-IHE appointment route, "
                "apart from an institution-approved family/medical-leave "
                "exception, holds an eligible U.S.-campus appointment by the "
                "deadline."
            ),
            inapplicable_message=(
                "all_non_exception_senior_key_have_eligible_ihe_appointments "
                "must be not_applicable for a non-IHE proposer."
            ),
        )
        _require_conditional(
            declarations,
            "no_pi_copi_or_senior_key_has_primary_appointment_at_overseas_us_ihe_branch",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_eligibility_overseas_us_ihe_primary_appointment",
            required_message=(
                "An IHE proposer must explicitly attest that no PI, co-PI, or "
                "other Senior/Key person has a primary appointment at an "
                "overseas branch campus of a U.S. IHE. This prohibited route "
                "is distinct from an essential, unfunded participant at a "
                "foreign academic institution."
            ),
            inapplicable_message=(
                "no_pi_copi_or_senior_key_has_primary_appointment_at_"
                "overseas_us_ihe_branch must be not_applicable for a non-IHE "
                "proposer."
            ),
        )

        has_foreign_academic_experts = _require_scoped_boolean(
            declarations,
            "has_foreign_academic_senior_key_or_collaborators",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_eligibility_foreign_academic_scope",
            required_message=(
                "An IHE proposer must declare "
                "has_foreign_academic_senior_key_or_collaborators as true or "
                "false."
            ),
            inapplicable_message=(
                "has_foreign_academic_senior_key_or_collaborators must be "
                "not_applicable for a non-IHE proposer."
            ),
        )
        if is_ihe and has_foreign_academic_experts is not None:
            _require_conditional(
                declarations,
                "all_foreign_academic_experts_are_essential_and_receive_no_nsf_support",
                applicable=has_foreign_academic_experts,
                findings=findings,
                rule="pesose_eligibility_foreign_academic_exception",
                required_message=(
                    "Every foreign-academic Senior/Key person or collaborator "
                    "using the exception must explicitly provide essential "
                    "expertise and receive no NSF support."
                ),
                inapplicable_message=(
                    "all_foreign_academic_experts_are_essential_and_receive_"
                    "no_nsf_support must be not_applicable when no foreign-"
                    "academic expert uses the exception."
                ),
            )
        elif not is_ihe:
            _require_not_applicable(
                declarations,
                "all_foreign_academic_experts_are_essential_and_receive_no_nsf_support",
                findings,
                "pesose_eligibility_foreign_academic_exception",
                "all_foreign_academic_experts_are_essential_and_receive_no_"
                "nsf_support must be not_applicable for a non-IHE proposer.",
            )

        has_leave_exception = _require_scoped_boolean(
            declarations,
            "has_senior_key_using_family_or_medical_leave_exception",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_eligibility_ihe_leave_exception_scope",
            required_message=(
                "An IHE proposer must declare whether any Senior/Key person "
                "uses the family or medical leave exception."
            ),
            inapplicable_message=(
                "has_senior_key_using_family_or_medical_leave_exception must "
                "be not_applicable for a non-IHE proposer."
            ),
        )
        if is_ihe and has_leave_exception is not None:
            _require_conditional(
                declarations,
                "proposing_ihe_determined_leave_exception_senior_key_eligible",
                applicable=has_leave_exception,
                findings=findings,
                rule="pesose_eligibility_ihe_leave_exception_determination",
                required_message=(
                    "The proposing IHE must explicitly determine that every "
                    "Senior/Key person using the family or medical leave "
                    "exception is eligible."
                ),
                inapplicable_message=(
                    "proposing_ihe_determined_leave_exception_senior_key_"
                    "eligible must be not_applicable when no Senior/Key person "
                    "uses the leave exception."
                ),
            )
        elif not is_ihe:
            _require_not_applicable(
                declarations,
                "proposing_ihe_determined_leave_exception_senior_key_eligible",
                findings,
                "pesose_eligibility_ihe_leave_exception_determination",
                "proposing_ihe_determined_leave_exception_senior_key_eligible "
                "must be not_applicable for a non-IHE proposer.",
            )

        funds_international_branch = _require_boolean(
            declarations,
            "requests_funding_for_international_branch_campus",
            findings,
            "pesose_eligibility_international_branch_scope",
            "Declare whether the proposal requests funding for an "
            "international branch campus of a U.S. IHE, including through a "
            "subaward or consultant.",
        )
        if funds_international_branch is not None:
            _require_conditional(
                declarations,
                "international_branch_benefit_and_us_campus_infeasibility_justified",
                applicable=funds_international_branch,
                findings=findings,
                rule="pesose_eligibility_international_branch_justification",
                required_message=(
                    "Funding for an international branch campus requires an "
                    "explicit justification of the benefit to the project "
                    "and why the activity cannot be performed at the U.S. "
                    "campus."
                ),
                inapplicable_message=(
                    "international_branch_benefit_and_us_campus_"
                    "infeasibility_justified must be not_applicable when no "
                    "international branch campus funding is requested."
                ),
            )
            _require_conditional(
                declarations,
                "international_branch_cover_sheet_box_checked",
                applicable=funds_international_branch,
                findings=findings,
                rule="pesose_eligibility_international_branch_cover_sheet",
                required_message=(
                    "When international branch funding is requested, the "
                    "Funding of an International Branch Campus cover-sheet "
                    "box must be checked."
                ),
                inapplicable_message=(
                    "international_branch_cover_sheet_box_checked must be "
                    "not_applicable when no international branch funding is "
                    "requested."
                ),
            )
            branch_countries = declarations.get(
                "international_branch_countries"
            )
            if funds_international_branch:
                valid_countries = (
                    not isinstance(branch_countries, (str, bytes))
                    and isinstance(branch_countries, Sequence)
                    and bool(branch_countries)
                    and all(
                        _non_placeholder_text(country)
                        for country in branch_countries
                    )
                )
                if not valid_countries:
                    findings.append(
                        _error(
                            "pesose_eligibility_international_branch_countries",
                            "International Activities must list at least one "
                            "non-placeholder country for international branch "
                            "campus funding.",
                        )
                    )
            elif not _is_not_applicable(branch_countries):
                findings.append(
                    _error(
                        "pesose_eligibility_international_branch_countries",
                        "international_branch_countries must be not_applicable "
                        "when no international branch funding is requested.",
                    )
                )
        _require_conditional(
            declarations,
            "pi_is_employee_of_proposing_organization",
            applicable=not is_ihe,
            findings=findings,
            rule="pesose_eligibility_pi_employee",
            required_message=(
                "For a non-IHE proposer, the PI must explicitly be an "
                "employee acting as an employee while performing PI duties."
            ),
            inapplicable_message=(
                "pi_is_employee_of_proposing_organization must be "
                "not_applicable for the IHE appointment route."
            ),
        )
        _require_conditional(
            declarations,
            "pi_normally_resident_in_us",
            applicable=not is_ihe,
            findings=findings,
            rule="pesose_eligibility_pi_us_residency",
            required_message=(
                "For a non-IHE proposer, the PI must explicitly be normally "
                "resident in the U.S."
            ),
            inapplicable_message=(
                "pi_normally_resident_in_us must be not_applicable for the "
                "IHE appointment route."
            ),
        )

        is_tribal_nation = organization_type == "tribal_nation"
        _require_conditional(
            declarations,
            "tribal_nation_is_federally_recognized",
            applicable=is_tribal_nation,
            findings=findings,
            rule="pesose_eligibility_tribal_recognition",
            required_message=(
                "A Tribal Nation proposer must explicitly attest that it is "
                "federally recognized."
            ),
            inapplicable_message=(
                "tribal_nation_is_federally_recognized must be not_applicable "
                "for this organization type."
            ),
        )

        is_federal_or_ffrdc = organization_type == "federal_agency_or_ffrdc"
        _require_conditional(
            declarations,
            "federal_ffrdc_pappg_ie2_review_completed",
            applicable=is_federal_or_ffrdc,
            findings=findings,
            rule="pesose_eligibility_federal_ffrdc_review",
            required_message=(
                "A federal agency or FFRDC proposer must explicitly attest "
                "that the PAPPG I.E.2 limitations and required exceptional-"
                "circumstances justification have been reviewed."
            ),
            inapplicable_message=(
                "federal_ffrdc_pappg_ie2_review_completed must be "
                "not_applicable for this organization type."
            ),
        )
        exception_routes = declarations.get(
            "federal_ffrdc_pappg_ie2_exception_routes"
        )
        if is_federal_or_ffrdc:
            valid_routes = (
                not isinstance(exception_routes, (str, bytes))
                and isinstance(exception_routes, Sequence)
                and bool(exception_routes)
                and all(
                    _normalize_token(route) in FEDERAL_FFRDC_EXCEPTION_ROUTES
                    for route in exception_routes
                )
            )
            if not valid_routes:
                findings.append(
                    _error(
                        "pesose_eligibility_federal_ffrdc_exception_route",
                        "A federal agency or FFRDC proposer must declare one "
                        "or more PAPPG I.E.2 exception routes: "
                        + ", ".join(FEDERAL_FFRDC_EXCEPTION_ROUTES)
                        + ".",
                    )
                )
        elif not _is_not_applicable(exception_routes):
            findings.append(
                _error(
                    "pesose_eligibility_federal_ffrdc_exception_route",
                    "federal_ffrdc_pappg_ie2_exception_routes must be "
                    "not_applicable for this organization type.",
                )
            )
        _require_conditional(
            declarations,
            "cognizant_nsf_program_officer_determined_federal_ffrdc_eligible_in_advance",
            applicable=is_federal_or_ffrdc,
            findings=findings,
            rule="pesose_eligibility_federal_ffrdc_advance_determination",
            required_message=(
                "A federal agency or FFRDC proposer must attest that the "
                "cognizant NSF Program Officer determined an applicable "
                "PAPPG I.E.2 exception in advance of proposal submission."
            ),
            inapplicable_message=(
                "cognizant_nsf_program_officer_determined_federal_ffrdc_"
                "eligible_in_advance must be not_applicable for this "
                "organization type."
            ),
        )

    _require_true(
        declarations,
        "pi_has_legal_right_to_work",
        findings,
        "pesose_eligibility_pi_legal_right_to_work",
        "The PI must explicitly attest a legal right to work in the U.S. for "
        "the proposing organization.",
    )
    has_other_funded_proposer_employees = _require_boolean(
        declarations,
        "has_other_pesose_funded_proposer_employees",
        findings,
        "pesose_eligibility_funded_employee_scope",
        "Declare has_other_pesose_funded_proposer_employees as true or false "
        "so the legal-right-to-work requirement can be evaluated for "
        "employees of the proposing organization.",
    )
    if has_other_funded_proposer_employees is not None:
        _require_conditional(
            declarations,
            "all_other_pesose_funded_proposer_employees_have_legal_right_to_work",
            applicable=has_other_funded_proposer_employees,
            findings=findings,
            rule="pesose_eligibility_funded_employee_work_authorization",
            required_message=(
                "Every other employee of the proposing organization receiving "
                "PESOSE support must attest a legal right to work in the U.S. "
                "for the proposing organization."
            ),
            inapplicable_message=(
                "all_other_pesose_funded_proposer_employees_have_legal_right_"
                "to_work must be not_applicable when there are no other "
                "PESOSE-funded employees of the proposing organization."
            ),
        )
    return findings


def validate_budget_scope_declarations(
    eligibility: Mapping[str, object] | None,
    budget: Mapping[str, object] | None,
) -> list[PESOSEFinding]:
    """Reject explicit eligibility scopes contradicted by budget evidence.

    The budget validator owns the full line-item schema. This narrow cross-file
    check only reconciles two declarations whose applicability can be proved
    from a positive Line B request or a funded subaward entry.
    """
    if not isinstance(eligibility, Mapping) or not isinstance(budget, Mapping):
        return []

    findings: list[PESOSEFinding] = []
    if (
        _budget_has_positive_line_b_personnel(budget)
        and eligibility.get("has_other_pesose_funded_proposer_employees")
        is False
    ):
        findings.append(
            _error(
                "pesose_eligibility_funded_employee_scope_contradiction",
                "budget.yaml contains a positive Line B personnel request, "
                "but has_other_pesose_funded_proposer_employees is false. "
                "Declare the funded-proposer-employee scope as true and "
                "attest work authorization for every other funded employee "
                "of the proposing organization.",
            )
        )

    if (
        _budget_has_subaward_entry(budget)
        and eligibility.get("has_other_nsf_funded_organizations") is False
    ):
        findings.append(
            _error(
                "pesose_eligibility_subaward_scope_contradiction",
                "budget.yaml contains a funded subaward request, but "
                "has_other_nsf_funded_organizations is false. Declare the "
                "funded-organization scope as true and complete the subaward "
                "structure and eligibility attestations.",
            )
        )
    return findings


def validate_senior_key_document_manifest(
    manifest: Mapping[str, Mapping[str, object]] | None,
    declared_senior_key_people: Sequence[object] | None = None,
    actual_document_files: Sequence[str] | None = None,
    actual_synergistic_page_counts: Mapping[str, int] | None = None,
    proposal_submission_date: str | None = None,
) -> list[PESOSEFinding]:
    """Validate the PAPPG II.D.2.h document set for each Senior/Key person."""
    if not isinstance(manifest, Mapping):
        return [
            _error(
                "pesose_senior_key_document_manifest",
                "The Senior/Key document manifest must be a mapping keyed by "
                "person name.",
            )
        ]

    findings: list[PESOSEFinding] = []
    submission_date = _parse_iso_date(proposal_submission_date)
    if submission_date is None:
        findings.append(
            _error(
                "pesose_proposal_submission_date",
                "Provide proposal_submission_date in YYYY-MM-DD format so "
                "research-security training recency can be calculated.",
            )
        )
    if not manifest:
        findings.append(
            _error(
                "pesose_senior_key_document_manifest",
                "The Senior/Key document manifest must contain at least one "
                "person.",
            )
        )

    manifest_people: set[str] = set()
    document_paths: dict[str, str] = {}
    for person, documents in manifest.items():
        if not _non_placeholder_text(person):
            findings.append(
                _error(
                    "pesose_senior_key_person_name",
                    "Every Senior/Key document-manifest key must be a non-"
                    "placeholder person name.",
                )
            )
            person_label = repr(person)
        else:
            assert isinstance(person, str)
            normalized_person = _normalize_space(person).casefold()
            person_label = person
            if normalized_person in manifest_people:
                findings.append(
                    _error(
                        "pesose_senior_key_duplicate_person",
                        f"Senior/Key document manifest repeats {person!r} "
                        "after name normalization.",
                    )
                )
            manifest_people.add(normalized_person)

        if not isinstance(documents, Mapping):
            findings.append(
                _error(
                    "pesose_senior_key_document_entry",
                    f"Senior/Key entry {person_label!r} must be a mapping.",
                )
            )
            continue

        for field_name in SENIOR_KEY_DOCUMENT_FIELDS:
            file_ref = documents.get(field_name)
            normalized_path = _manifest_path(file_ref)
            if normalized_path is None:
                findings.append(
                    _error(
                        f"pesose_senior_key_{field_name}",
                        f"Senior/Key person {person_label!r} must provide a "
                        f"project-relative {field_name}.",
                    )
                )
                continue
            required_suffix = (
                ".xlsx"
                if field_name == "collaborators_and_other_affiliations_file"
                else ".pdf"
            )
            if not normalized_path.casefold().endswith(required_suffix):
                findings.append(
                    _error(
                        "pesose_senior_key_document_format",
                        f"Senior/Key {field_name} for {person_label!r} must "
                        f"use the required {required_suffix} format.",
                    )
                )
            if normalized_path in document_paths:
                findings.append(
                    _error(
                        "pesose_senior_key_duplicate_document_file",
                        f"Senior/Key document path {file_ref!r} is also used "
                        f"for {document_paths[normalized_path]}.",
                    )
                )
            else:
                document_paths[normalized_path] = (
                    f"{person_label!r} {field_name}"
                )

        if (
            documents.get("all_proposals_and_active_projects_disclosed")
            is not True
        ):
            findings.append(
                _error(
                    "pesose_senior_key_current_pending_disclosure",
                    f"Senior/Key person {person_label!r} must explicitly "
                    "attest that Current and Pending (Other) Support discloses "
                    "all proposals and active projects, including this "
                    "proposal and support from every source.",
                )
            )
        for key, description in (
            (
                "biographical_sketch_sciencv_certified",
                "the Biographical Sketch was prepared and certified in "
                "SciENcv",
            ),
            (
                "current_and_pending_support_sciencv_certified",
                "Current and Pending (Other) Support was prepared and "
                "certified in SciENcv",
            ),
            (
                "current_and_pending_support_current_accurate_complete",
                "Current and Pending (Other) Support is current, accurate, "
                "and complete",
            ),
            (
                "coa_uses_unaltered_nsf_template",
                "COA uses the separate, unaltered NSF template",
            ),
            (
                "not_a_party_to_mftrp",
                "the person is not a party to a malign foreign talent "
                "recruitment program",
            ),
        ):
            if documents.get(key) is not True:
                findings.append(
                    _error(
                        f"pesose_senior_key_{key}",
                        f"Senior/Key person {person_label!r} must explicitly "
                        f"attest that {description}.",
                    )
                )

        synergistic_page_count = documents.get(
            "synergistic_activities_page_count"
        )
        if (
            isinstance(synergistic_page_count, bool)
            or not isinstance(synergistic_page_count, int)
            or synergistic_page_count != 1
        ):
            findings.append(
                _error(
                    "pesose_senior_key_synergistic_activities_page_limit",
                    f"Senior/Key person {person_label!r} must declare a one-"
                    "page Synergistic Activities document.",
                )
            )
        synergistic_example_count = documents.get(
            "synergistic_activities_example_count"
        )
        if (
            isinstance(synergistic_example_count, bool)
            or not isinstance(synergistic_example_count, int)
            or not 1 <= synergistic_example_count <= 5
        ):
            findings.append(
                _error(
                    "pesose_senior_key_synergistic_activities_examples",
                    f"Senior/Key person {person_label!r} must declare one to "
                    "five distinct Synergistic Activities examples.",
                )
            )

        training_date_value = documents.get(
            "research_security_training_completion_date"
        )
        training_date = _parse_iso_date(training_date_value)
        if training_date is None:
            findings.append(
                _error(
                    "pesose_senior_key_research_security_training_date",
                    f"Senior/Key person {person_label!r} must provide the "
                    "qualifying research-security training completion date "
                    "in YYYY-MM-DD format.",
                )
            )
        recency_attested = (
            documents.get(
                "research_security_training_within_12_months_before_submission"
            )
            is True
        )
        recency_calculated = (
            training_date is not None
            and submission_date is not None
            and _one_year_before(submission_date)
            <= training_date
            <= submission_date
        )
        if not recency_attested or (
            training_date is not None
            and submission_date is not None
            and not recency_calculated
        ):
            findings.append(
                _error(
                    "pesose_senior_key_research_security_training_recency",
                    f"Senior/Key person {person_label!r} must attest that "
                    "qualifying research-security training was completed "
                    "within 12 months before proposal submission.",
                )
            )
        training_evidence = documents.get(
            "research_security_training_evidence_reference"
        )
        if training_evidence is not None and not _non_placeholder_text(
            training_evidence
        ):
            findings.append(
                _warning(
                    "pesose_senior_key_research_security_training_evidence",
                    f"Optional internal training-evidence reference for "
                    f"Senior/Key person {person_label!r} is blank or a "
                    "placeholder.",
                )
            )

    if declared_senior_key_people is not None:
        findings += _reconcile_senior_key_people(
            manifest_people, declared_senior_key_people
        )
    if actual_document_files is not None:
        findings += _reconcile_senior_key_file_inventory(
            set(document_paths), actual_document_files
        )
    if actual_synergistic_page_counts is not None:
        findings += _reconcile_synergistic_page_counts(
            manifest, actual_synergistic_page_counts
        )
    return findings


def _reconcile_senior_key_people(
    manifest_people: set[str], declared_people: Sequence[object]
) -> list[PESOSEFinding]:
    if isinstance(declared_people, (str, bytes)) or not isinstance(
        declared_people, Sequence
    ):
        return [
            _error(
                "pesose_senior_key_declared_roster",
                "declared_senior_key_people must be a sequence of person "
                "names or mappings containing full_name.",
            )
        ]

    findings: list[PESOSEFinding] = []
    declared_names: set[str] = set()
    for index, entry in enumerate(declared_people, 1):
        name = (
            entry.get("full_name", entry.get("Full name"))
            if isinstance(entry, Mapping)
            else entry
        )
        if not _non_placeholder_text(name):
            findings.append(
                _error(
                    "pesose_senior_key_declared_roster",
                    f"Declared Senior/Key roster entry {index} must provide "
                    "a non-placeholder person name.",
                )
            )
            continue
        assert isinstance(name, str)
        normalized_name = _normalize_space(name).casefold()
        if normalized_name in declared_names:
            findings.append(
                _error(
                    "pesose_senior_key_declared_roster_duplicate",
                    f"Declared Senior/Key roster repeats {name!r}.",
                )
            )
        declared_names.add(normalized_name)

    missing_people = sorted(declared_names - manifest_people)
    extra_people = sorted(manifest_people - declared_names)
    if missing_people or extra_people:
        details = []
        if missing_people:
            details.append(
                "declared people missing documents: "
                + ", ".join(missing_people)
            )
        if extra_people:
            details.append(
                "document entries outside declared roster: "
                + ", ".join(extra_people)
            )
        findings.append(
            _error(
                "pesose_senior_key_roster_reconciliation",
                "Senior/Key documents do not reconcile to the declared roster "
                "(" + "; ".join(details) + ").",
            )
        )
    return findings


def _reconcile_senior_key_file_inventory(
    manifest_files: set[str], actual_document_files: Sequence[str]
) -> list[PESOSEFinding]:
    if isinstance(actual_document_files, (str, bytes)) or not isinstance(
        actual_document_files, Sequence
    ):
        return [
            _error(
                "pesose_senior_key_file_inventory",
                "actual_document_files must be a sequence of project-relative "
                "Senior/Key document paths.",
            )
        ]

    findings: list[PESOSEFinding] = []
    actual_files: set[str] = set()
    for index, file_ref in enumerate(actual_document_files, 1):
        normalized = _manifest_path(file_ref)
        if normalized is None:
            findings.append(
                _error(
                    "pesose_senior_key_file_inventory",
                    f"Actual Senior/Key file entry {index} must be a non-"
                    "placeholder project-relative path.",
                )
            )
            continue
        if normalized in actual_files:
            findings.append(
                _error(
                    "pesose_senior_key_duplicate_actual_file",
                    f"Actual Senior/Key file inventory repeats {file_ref!r} "
                    "after normalization.",
                )
            )
        actual_files.add(normalized)

    missing_metadata = sorted(actual_files - manifest_files)
    missing_files = sorted(manifest_files - actual_files)
    if missing_metadata or missing_files:
        details = []
        if missing_metadata:
            details.append(
                "files outside manifest: " + ", ".join(missing_metadata)
            )
        if missing_files:
            details.append(
                "manifest paths without files: " + ", ".join(missing_files)
            )
        findings.append(
            _error(
                "pesose_senior_key_manifest_file_reconciliation",
                "Senior/Key document manifest and actual file inventory "
                "differ (" + "; ".join(details) + ").",
            )
        )
    return findings


def _reconcile_synergistic_page_counts(
    manifest: Mapping[str, Mapping[str, object]],
    actual_page_counts: Mapping[str, int],
) -> list[PESOSEFinding]:
    if not isinstance(actual_page_counts, Mapping):
        return [
            _error(
                "pesose_senior_key_actual_page_counts",
                "Actual Synergistic Activities page counts must be a mapping "
                "from PDF path to integer page count.",
            )
        ]

    expected: dict[str, object] = {}
    for documents in manifest.values():
        if not isinstance(documents, Mapping):
            continue
        normalized = _manifest_path(
            documents.get("synergistic_activities_file")
        )
        if normalized is not None:
            expected[normalized] = documents.get(
                "synergistic_activities_page_count"
            )

    actual: dict[str, int] = {}
    findings: list[PESOSEFinding] = []
    for file_ref, page_count in actual_page_counts.items():
        normalized = _manifest_path(file_ref)
        if normalized is None:
            findings.append(
                _error(
                    "pesose_senior_key_actual_page_counts",
                    f"Actual Synergistic Activities page-count key "
                    f"{file_ref!r} is not a valid project-relative path.",
                )
            )
            continue
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count != 1
        ):
            findings.append(
                _error(
                    "pesose_senior_key_actual_synergistic_page_limit",
                    f"Actual Synergistic Activities PDF {file_ref!r} must "
                    "contain one page.",
                )
            )
        actual[normalized] = page_count

    if set(actual) != set(expected):
        findings.append(
            _error(
                "pesose_senior_key_synergistic_page_reconciliation",
                "Actual Synergistic Activities page-count keys must exactly "
                "match the manifest's Synergistic Activities paths.",
            )
        )
    for path in set(actual) & set(expected):
        if actual[path] != expected[path]:
            findings.append(
                _error(
                    "pesose_senior_key_synergistic_page_reconciliation",
                    f"Declared and actual Synergistic Activities page counts "
                    f"differ for {path!r}.",
                )
            )
    return findings


def validate_prior_nsf_support(
    declarations: Mapping[str, object] | None,
) -> list[PESOSEFinding]:
    """Validate manual review of PAPPG II.D.2.d(iii)'s six elements."""
    if not isinstance(declarations, Mapping):
        return [
            _error(
                "pesose_prior_nsf_support_declarations",
                "Results from Prior NSF Support declarations must be a "
                "mapping.",
            )
        ]

    findings: list[PESOSEFinding] = []
    has_covered_support = _require_boolean(
        declarations,
        "has_pi_or_copi_with_current_or_recent_nsf_support",
        findings,
        "pesose_prior_nsf_support_scope",
        "Declare whether any PI or co-PI has current NSF funding (including "
        "a no-cost extension) or an NSF award ending in the past five years.",
    )
    if has_covered_support is None:
        return findings

    if not has_covered_support:
        for key in (
            "results_from_prior_nsf_support_included",
            "all_covered_pi_copi_awards_included",
            "results_from_prior_nsf_support_within_five_pages",
            *PRIOR_SUPPORT_REVIEW_ATTESTATIONS[:-1],
            "is_renewal_proposal",
            PRIOR_SUPPORT_REVIEW_ATTESTATIONS[-1],
        ):
            _require_not_applicable(
                declarations,
                key,
                findings,
                "pesose_prior_nsf_support_not_applicable",
                f"{key} must be not_applicable when no PI or co-PI has "
                "covered prior or current NSF support.",
            )
        return findings

    _require_true(
        declarations,
        "results_from_prior_nsf_support_included",
        findings,
        "pesose_prior_nsf_support_presence",
        "Results from Prior NSF Support must be included when a PI or co-PI "
        "has covered prior or current NSF support.",
    )
    _require_true(
        declarations,
        "all_covered_pi_copi_awards_included",
        findings,
        "pesose_prior_nsf_support_covered_people",
        "Attest that Results from Prior NSF Support includes one qualifying "
        "award for every covered PI and co-PI (the most closely related award "
        "when a person has more than one).",
    )
    _require_true(
        declarations,
        "results_from_prior_nsf_support_within_five_pages",
        findings,
        "pesose_prior_nsf_support_page_limit",
        "Attest that Results from Prior NSF Support occupies no more than five "
        "pages within the Project Description.",
    )
    for key in PRIOR_SUPPORT_REVIEW_ATTESTATIONS[:-1]:
        _require_true(
            declarations,
            key,
            findings,
            f"pesose_prior_nsf_support_{key}",
            f"A manual reviewer must explicitly attest {key}: true for "
            "Results from Prior NSF Support.",
        )

    is_renewal = _require_boolean(
        declarations,
        "is_renewal_proposal",
        findings,
        "pesose_prior_nsf_support_renewal_scope",
        "Declare is_renewal_proposal as true or false when Results from Prior "
        "NSF Support are required.",
    )
    if is_renewal is not None:
        _require_conditional(
            declarations,
            PRIOR_SUPPORT_REVIEW_ATTESTATIONS[-1],
            applicable=is_renewal,
            findings=findings,
            rule="pesose_prior_nsf_support_renewal_relationship",
            required_message=(
                "A renewal proposal must explicitly attest that the relation "
                "of completed work to proposed work is described."
            ),
            inapplicable_message=(
                "renewal_relationship_addressed must be not_applicable when "
                "the proposal is not for renewed support."
            ),
        )
    return findings


def validate_mentoring_plan(
    declarations: Mapping[str, object] | None,
    evidence: Mapping[str, object] | None = None,
) -> list[PESOSEFinding]:
    """Validate the conditional unified Mentoring Plan determination."""
    if not isinstance(declarations, Mapping):
        return [
            _error(
                "pesose_mentoring_plan_declarations",
                "Mentoring Plan declarations must be a mapping.",
            )
        ]

    findings: list[PESOSEFinding] = []
    funds_trainees = _require_boolean(
        declarations,
        "funds_postdoctoral_scholars_or_graduate_students",
        findings,
        "pesose_mentoring_plan_scope",
        "Declare whether the proposal requests support for any postdoctoral "
        "scholar or graduate student at any participating organization.",
    )
    if funds_trainees is None:
        return findings

    _require_conditional(
        declarations,
        "unified_mentoring_plan_present",
        applicable=funds_trainees,
        findings=findings,
        rule="pesose_mentoring_plan_presence",
        required_message=(
            "A single unified Mentoring Plan must be present when the proposal "
            "supports postdoctoral scholars or graduate students."
        ),
        inapplicable_message=(
            "unified_mentoring_plan_present must be not_applicable when no "
            "postdoctoral scholar or graduate student is supported."
        ),
    )
    page_count = declarations.get("mentoring_plan_page_count")
    if funds_trainees:
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count != 1
        ):
            findings.append(
                _error(
                    "pesose_mentoring_plan_page_limit",
                    "The unified Mentoring Plan must declare a page_count of "
                    "exactly one or less; an included plan must have one page.",
                )
            )
    elif not _is_not_applicable(page_count):
        findings.append(
            _error(
                "pesose_mentoring_plan_page_limit",
                "mentoring_plan_page_count must be not_applicable when no "
                "Mentoring Plan is required.",
            )
        )
    if evidence is not None:
        findings += _validate_mentoring_plan_evidence(
            evidence, funds_trainees, page_count
        )
    return findings


def _validate_mentoring_plan_evidence(
    evidence: Mapping[str, object],
    funds_trainees: bool,
    declared_page_count: object,
) -> list[PESOSEFinding]:
    if not isinstance(evidence, Mapping):
        return [
            _error(
                "pesose_mentoring_plan_evidence",
                "Mentoring Plan evidence must be a mapping.",
            )
        ]

    findings: list[PESOSEFinding] = []
    file_present = evidence.get("file_present")
    actual_page_count = evidence.get("page_count")
    if not isinstance(file_present, bool):
        findings.append(
            _error(
                "pesose_mentoring_plan_file_reconciliation",
                "Mentoring Plan evidence must declare file_present as true "
                "or false.",
            )
        )
    elif file_present is not funds_trainees:
        findings.append(
            _error(
                "pesose_mentoring_plan_file_reconciliation",
                "Actual Mentoring Plan file presence does not match whether "
                "the proposal funds postdoctoral scholars or graduate "
                "students.",
            )
        )

    if funds_trainees:
        if (
            isinstance(actual_page_count, bool)
            or not isinstance(actual_page_count, int)
            or actual_page_count != 1
        ):
            findings.append(
                _error(
                    "pesose_mentoring_plan_actual_page_limit",
                    "Actual Mentoring Plan evidence must report one page.",
                )
            )
        elif declared_page_count != actual_page_count:
            findings.append(
                _error(
                    "pesose_mentoring_plan_page_reconciliation",
                    "Declared and actual Mentoring Plan page counts differ.",
                )
            )
    elif not _is_not_applicable(actual_page_count):
        findings.append(
            _error(
                "pesose_mentoring_plan_actual_page_limit",
                "Mentoring Plan evidence page_count must be not_applicable "
                "when no file is required.",
            )
        )
    return findings


def validate_supplement_1(
    declarations: Mapping[str, object] | None,
    *,
    organization_type: object | None = None,
) -> list[PESOSEFinding]:
    """Validate NSF 26-200 Confucius-Institute and drone declarations."""
    if not isinstance(declarations, Mapping):
        return [
            _error(
                "pesose_supplement_1_declarations",
                "NSF PAPPG Supplement 1 declarations must be a mapping.",
            )
        ]

    findings: list[PESOSEFinding] = []
    is_ihe = _require_boolean(
        declarations,
        "proposing_organization_is_ihe",
        findings,
        "pesose_supplement_1_ihe_scope",
        "Declare proposing_organization_is_ihe as true or false.",
    )
    canonical_type = _canonical_organization_type(organization_type)
    if is_ihe is not None and canonical_type is not None:
        expected_is_ihe = canonical_type == "institution_of_higher_education"
        if is_ihe is not expected_is_ihe:
            findings.append(
                _error(
                    "pesose_supplement_1_ihe_reconciliation",
                    "proposing_organization_is_ihe does not match the "
                    "eligibility organization_type.",
                )
            )

    _require_true(
        declarations,
        "foreign_affiliation_and_support_disclosure_documentation_maintained",
        findings,
        "pesose_supplement_1_research_security_documentation",
        "The proposer must attest that it maintains supporting documentation "
        "for reported foreign appointments, employment, talent programs, and "
        "Current and Pending (Other) Support disclosures.",
    )
    _require_true(
        declarations,
        "aor_certifies_all_senior_key_research_security_training_completed",
        findings,
        "pesose_supplement_1_research_security_training_aor",
        "The AOR must certify that every Senior/Key person completed "
        "qualifying research-security training within 12 months before "
        "proposal submission.",
    )
    _require_true(
        declarations,
        "aor_certifies_all_senior_key_mftrp_certifications_complete",
        findings,
        "pesose_supplement_1_mftrp_aor",
        "The AOR must certify that every Senior/Key person was made aware of "
        "and complied with the malign foreign talent recruitment program "
        "certification requirement.",
    )
    if is_ihe is not None:
        _require_conditional(
            declarations,
            "aor_certifies_ihe_recr_training_plan",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_supplement_1_ihe_recr_plan",
            required_message=(
                "For an IHE proposer, the AOR must certify that the required "
                "Responsible and Ethical Conduct of Research training plan is "
                "in place."
            ),
            inapplicable_message=(
                "aor_certifies_ihe_recr_training_plan must be not_applicable "
                "for a non-IHE proposer."
            ),
        )

    if is_ihe is not None:
        maintains_confucius_agreement = _require_scoped_boolean(
            declarations,
            "ihe_maintains_confucius_institute_contract_or_agreement",
            applicable=is_ihe,
            findings=findings,
            rule="pesose_supplement_1_confucius_scope",
            required_message=(
                "An IHE must declare whether it maintains a contract or "
                "agreement with a Confucius Institute."
            ),
            inapplicable_message=(
                "ihe_maintains_confucius_institute_contract_or_agreement "
                "must be not_applicable for a non-IHE proposer."
            ),
        )
        if is_ihe and maintains_confucius_agreement is not None:
            director_waiver = declarations.get(
                "nsf_director_confucius_institute_waiver_approved"
            )
            dod_exemption = declarations.get(
                "dod_section_1062_waiver_requirements_fulfilled"
            )
            if maintains_confucius_agreement:
                if director_waiver is not True and dod_exemption is not True:
                    findings.append(
                        _error(
                            "pesose_supplement_1_confucius_waiver",
                            "An IHE maintaining a Confucius Institute "
                            "agreement must have either an NSF Director waiver "
                            "or fulfill the DoD section 1062 waiver "
                            "requirements.",
                        )
                    )
            else:
                for key in (
                    "nsf_director_confucius_institute_waiver_approved",
                    "dod_section_1062_waiver_requirements_fulfilled",
                ):
                    _require_not_applicable(
                        declarations,
                        key,
                        findings,
                        "pesose_supplement_1_confucius_waiver",
                        f"{key} must be not_applicable when the IHE maintains "
                        "no Confucius Institute agreement.",
                    )
        elif not is_ihe:
            for key in (
                "nsf_director_confucius_institute_waiver_approved",
                "dod_section_1062_waiver_requirements_fulfilled",
            ):
                _require_not_applicable(
                    declarations,
                    key,
                    findings,
                    "pesose_supplement_1_confucius_waiver",
                    f"{key} must be not_applicable for a non-IHE proposer.",
                )

    includes_nsf_funded_drone_activity = _require_boolean(
        declarations,
        "project_includes_nsf_funded_unmanned_aircraft_procurement_or_operation",
        findings,
        "pesose_supplement_1_drone_scope",
        "Declare whether the project includes any NSF-funded procurement or "
        "operation of an unmanned aircraft system.",
    )
    if includes_nsf_funded_drone_activity is not None:
        _require_conditional(
            declarations,
            "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems",
            applicable=includes_nsf_funded_drone_activity,
            findings=findings,
            rule="pesose_supplement_1_covered_foreign_drones",
            required_message=(
                "When the project includes NSF-funded unmanned-aircraft "
                "procurement or operation, attest that NSF funds will not "
                "procure a system manufactured or assembled by a covered "
                "foreign entity or support operation of such a system."
            ),
            inapplicable_message=(
                "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems "
                "must be not_applicable when the project includes no NSF-"
                "funded unmanned-aircraft procurement or operation."
            ),
        )
    return findings


def validate_letter_manifest(
    manifest: Mapping[str, Mapping[str, object]] | None,
    facilities_continuation: Mapping[str, object] | None,
    actual_letter_files: Sequence[str] | None = None,
    actual_page_counts: Mapping[str, int] | None = None,
) -> list[PESOSEFinding]:
    """Validate NSF 26-506 V.A letter metadata without opening the files."""
    if not isinstance(manifest, Mapping):
        return [
            _error(
                "pesose_letters_manifest",
                "The PESOSE letter manifest must be a mapping keyed by "
                "project-relative file paths.",
            )
        ]

    findings: list[PESOSEFinding] = []
    if not 3 <= len(manifest) <= 5:
        findings.append(
            _error(
                "pesose_letters_count",
                "PESOSE requires three to five letter-manifest entries; "
                f"found {len(manifest)}.",
            )
        )

    normalized_files: dict[str, str] = {}
    required_text = ("writer_name", "affiliation", "project_relationship")
    readiness_text = ("past_contribution", "continuing_contribution")
    for file_ref, metadata in manifest.items():
        normalized = _manifest_path(file_ref)
        label = str(file_ref) if isinstance(file_ref, str) else repr(file_ref)
        if normalized is None:
            findings.append(
                _error(
                    "pesose_letters_file_reference",
                    f"Letter manifest key {label!r} must be a non-placeholder "
                    "project-relative file path.",
                )
            )
        elif normalized in normalized_files:
            findings.append(
                _error(
                    "pesose_letters_duplicate_file",
                    f"Letter manifest paths {normalized_files[normalized]!r} "
                    f"and {label!r} refer to the same file.",
                )
            )
        else:
            normalized_files[normalized] = label

        if not isinstance(metadata, Mapping):
            findings.append(
                _error(
                    "pesose_letters_entry",
                    f"Letter {label!r} metadata must be a mapping.",
                )
            )
            continue

        for key in required_text:
            if not _non_placeholder_text(metadata.get(key)):
                findings.append(
                    _error(
                        f"pesose_letters_{key}",
                        f"Letter {label!r} must provide a non-placeholder "
                        f"{key}.",
                    )
                )
        for key in readiness_text:
            if not _non_placeholder_text(metadata.get(key)):
                findings.append(
                    _warning(
                        f"pesose_letters_{key}",
                        f"Letter {label!r} should provide a non-placeholder "
                        f"{key} for submission readiness.",
                    )
                )
        page_count = metadata.get("page_count")
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or not 1 <= page_count <= 2
        ):
            findings.append(
                _error(
                    "pesose_letters_page_limit",
                    f"Letter {label!r} must declare an integer page_count "
                    "from one through two.",
                )
            )
        if (
            metadata.get("independent_current_third_party_user_or_contributor")
            is not True
        ):
            findings.append(
                _error(
                    "pesose_letters_independent_current_third_party",
                    f"Letter {label!r} must explicitly attest that its writer "
                    "is an independent current third-party user or contributor.",
                )
            )

    findings += _validate_facilities_continuation(
        facilities_continuation, set(normalized_files)
    )
    reconciliation_manifest: dict[str, Mapping[str, object]] = dict(manifest)
    expected_files = set(normalized_files)
    if (
        isinstance(facilities_continuation, Mapping)
        and facilities_continuation.get("depends_on_facilities_after_award")
        is True
    ):
        facilities_file = _manifest_path(
            facilities_continuation.get("continuation_letter_file")
        )
        if facilities_file is not None:
            expected_files.add(facilities_file)
            if facilities_file not in normalized_files:
                reconciliation_manifest[facilities_file] = (
                    facilities_continuation
                )
    if actual_letter_files is not None:
        findings += _reconcile_letter_file_inventory(
            expected_files, actual_letter_files
        )
    if actual_page_counts is not None:
        findings += _reconcile_letter_page_counts(
            reconciliation_manifest, actual_page_counts
        )
    return findings


def _validate_facilities_continuation(
    declarations: Mapping[str, object] | None,
    manifest_files: set[str],
) -> list[PESOSEFinding]:
    if not isinstance(declarations, Mapping):
        return [
            _error(
                "pesose_letters_facilities_declarations",
                "Facilities-continuation declarations must be a mapping.",
            )
        ]

    findings: list[PESOSEFinding] = []
    depends = _require_boolean(
        declarations,
        "depends_on_facilities_after_award",
        findings,
        "pesose_letters_facilities_scope",
        "Declare depends_on_facilities_after_award as true or false.",
    )
    if depends is None:
        return findings

    letter_file = declarations.get("continuation_letter_file")
    if depends:
        normalized = _manifest_path(letter_file)
        if normalized is None:
            findings.append(
                _warning(
                    "pesose_letters_facilities_file",
                    "A project depending on facilities after the award should "
                    "identify a project-relative continuation_letter_file.",
                )
            )
        elif normalized not in manifest_files:
            for key in ("writer_name", "affiliation", "project_relationship"):
                if not _non_placeholder_text(declarations.get(key)):
                    findings.append(
                        _error(
                            f"pesose_letters_facilities_{key}",
                            "A separately declared facilities-continuation "
                            f"letter must provide a non-placeholder {key}.",
                        )
                    )
            page_count = declarations.get("page_count")
            if (
                isinstance(page_count, bool)
                or not isinstance(page_count, int)
                or not 1 <= page_count <= 2
            ):
                findings.append(
                    _error(
                        "pesose_letters_facilities_page_limit",
                        "A separately declared facilities-continuation "
                        "letter must declare an integer page_count from one "
                        "through two.",
                    )
                )
        if declarations.get("extent_and_term_described") is not True:
            findings.append(
                _warning(
                    "pesose_letters_facilities_extent_term",
                    "The facilities continuation letter should describe both "
                    "the extent and term of provision.",
                )
            )
    else:
        if not _is_not_applicable(letter_file):
            findings.append(
                _warning(
                    "pesose_letters_facilities_file",
                    "continuation_letter_file must be not_applicable when the "
                    "OSE will not depend on facilities after the award.",
                )
            )
        if not _is_not_applicable(
            declarations.get("extent_and_term_described")
        ):
            findings.append(
                _warning(
                    "pesose_letters_facilities_extent_term",
                    "extent_and_term_described should be not_applicable when "
                    "no facilities-continuation letter is required.",
                )
            )
    return findings


def _reconcile_letter_file_inventory(
    manifest_files: set[str], actual_letter_files: Sequence[str]
) -> list[PESOSEFinding]:
    if isinstance(actual_letter_files, (str, bytes)) or not isinstance(
        actual_letter_files, Sequence
    ):
        return [
            _error(
                "pesose_letters_file_inventory",
                "actual_letter_files must be a sequence of project-relative "
                "file paths.",
            )
        ]

    findings: list[PESOSEFinding] = []
    actual_files: set[str] = set()
    for index, file_ref in enumerate(actual_letter_files, 1):
        normalized = _manifest_path(file_ref)
        if normalized is None:
            findings.append(
                _error(
                    "pesose_letters_file_inventory",
                    f"Actual letter-file entry {index} must be a non-"
                    "placeholder project-relative file path.",
                )
            )
            continue
        if normalized in actual_files:
            findings.append(
                _error(
                    "pesose_letters_duplicate_actual_file",
                    f"Actual letter-file inventory repeats {file_ref!r} "
                    "after path normalization.",
                )
            )
        actual_files.add(normalized)

    missing_metadata = sorted(actual_files - manifest_files)
    missing_files = sorted(manifest_files - actual_files)
    if missing_metadata or missing_files:
        details = []
        if missing_metadata:
            details.append(
                "files without manifest metadata: "
                + ", ".join(missing_metadata)
            )
        if missing_files:
            details.append(
                "manifest entries without files: " + ", ".join(missing_files)
            )
        findings.append(
            _error(
                "pesose_letters_manifest_file_reconciliation",
                "Letter manifest and actual file inventory differ ("
                + "; ".join(details)
                + ").",
            )
        )
    return findings


def _reconcile_letter_page_counts(
    manifest: Mapping[str, Mapping[str, object]],
    actual_page_counts: Mapping[str, int],
) -> list[PESOSEFinding]:
    if not isinstance(actual_page_counts, Mapping):
        return [
            _error(
                "pesose_letters_actual_page_counts",
                "actual_page_counts must map letter paths to integer PDF page "
                "counts.",
            )
        ]

    findings: list[PESOSEFinding] = []
    normalized_actual: dict[str, int] = {}
    for file_ref, page_count in actual_page_counts.items():
        normalized = _manifest_path(file_ref)
        if normalized is None:
            findings.append(
                _error(
                    "pesose_letters_actual_page_counts",
                    f"Actual page-count key {file_ref!r} is not a valid "
                    "project-relative path.",
                )
            )
            continue
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or not 1 <= page_count <= 2
        ):
            findings.append(
                _error(
                    "pesose_letters_actual_page_limit",
                    f"Actual letter {file_ref!r} must contain one or two "
                    "pages.",
                )
            )
        normalized_actual[normalized] = page_count

    normalized_manifest = {
        normalized: metadata
        for file_ref, metadata in manifest.items()
        if (normalized := _manifest_path(file_ref)) is not None
        and isinstance(metadata, Mapping)
    }
    if set(normalized_actual) != set(normalized_manifest):
        findings.append(
            _error(
                "pesose_letters_page_count_reconciliation",
                "Actual letter page-count keys must exactly match normalized "
                "manifest paths.",
            )
        )
    for path in set(normalized_actual) & set(normalized_manifest):
        declared = normalized_manifest[path].get("page_count")
        if declared != normalized_actual[path]:
            findings.append(
                _error(
                    "pesose_letters_page_count_reconciliation",
                    f"Declared and actual page counts differ for {path!r}.",
                )
            )
    return findings


def _validate_full_personnel_evidence(
    letter_manifest: Mapping[str, Mapping[str, object]] | None,
    declared_roster: Sequence[object] | None,
    declarations: Mapping[str, object] | None,
) -> list[PESOSEFinding]:
    findings: list[PESOSEFinding] = []
    roster_is_sequence = not isinstance(
        declared_roster, (str, bytes)
    ) and isinstance(declared_roster, Sequence)
    if not roster_is_sequence or not declared_roster:
        findings.append(
            _error(
                "pesose_personnel_declared_roster_required",
                "The full PESOSE validation requires a non-empty declared "
                "roster for reconciliation.",
            )
        )

    if not isinstance(declarations, Mapping):
        findings.append(
            _error(
                "pesose_personnel_completeness_declarations",
                "Personnel completeness declarations must be a mapping.",
            )
        )
    else:
        _require_true(
            declarations,
            "roster_includes_all_required_personnel_classes",
            findings,
            "pesose_personnel_roster_completeness",
            "Explicitly attest that the declared roster includes every "
            "applicable PI, co-PI, Senior/Key person, consultant, "
            "collaborator (including every letter writer), subawardee, "
            "postdoctoral researcher, and advisory-committee member.",
        )

    if not roster_is_sequence or not isinstance(letter_manifest, Mapping):
        return findings

    roster_names = set()
    assert declared_roster is not None
    for entry in declared_roster:
        parsed = _roster_entry(entry)
        if parsed is not None:
            roster_names.add(parsed[0])

    missing_writers = sorted(
        {
            _normalize_space(writer).casefold()
            for metadata in letter_manifest.values()
            if isinstance(metadata, Mapping)
            and isinstance((writer := metadata.get("writer_name")), str)
            and _non_placeholder_text(writer)
        }
        - roster_names
    )
    if missing_writers:
        findings.append(
            _error(
                "pesose_personnel_letter_writer_reconciliation",
                "Every letter writer must appear in the declared personnel "
                "roster; missing: " + ", ".join(missing_writers) + ".",
            )
        )
    return findings


def validate_personnel_table(
    markdown: str | None,
    declared_roster: Sequence[object] | None = None,
) -> list[PESOSEFinding]:
    """Validate personnel data while treating the suggested table as readiness."""
    if not isinstance(markdown, str) or not markdown.strip():
        return [
            _warning(
                "pesose_personnel_table_missing",
                "NSF 26-506 says the personnel list should be tabular; provide "
                "a non-placeholder Markdown table for submission readiness.",
            )
        ]

    lines = markdown.splitlines()
    table = _find_markdown_table(lines)
    if table is None:
        return [
            _warning(
                "pesose_personnel_table_missing",
                "No Markdown table with a header and separator row was found; "
                "manual review is needed to confirm all required personnel "
                "data.",
            )
        ]

    header_index, header = table
    findings: list[PESOSEFinding] = []
    normalized_header = tuple(
        _normalize_space(cell).casefold() for cell in header
    )
    expected_header = tuple(column.casefold() for column in PERSONNEL_COLUMNS)
    headers_identified = all(
        column in normalized_header for column in expected_header
    )
    if headers_identified:
        field_indexes = tuple(
            normalized_header.index(column) for column in expected_header
        )
    elif len(header) >= len(PERSONNEL_COLUMNS):
        field_indexes = (0, 1, 2)
    else:
        findings.append(
            _warning(
                "pesose_personnel_table_columns",
                "The personnel table does not expose three columns that can "
                "be manually reviewed as name, organization, and role.",
            )
        )
        return findings

    if (
        not headers_identified
        or field_indexes != (0, 1, 2)
        or len(header) != 3
    ):
        findings.append(
            _warning(
                "pesose_personnel_table_columns",
                "For submission readiness, personnel table columns should be "
                "labeled, in order: " + "; ".join(PERSONNEL_COLUMNS) + ".",
            )
        )

    complete_rows: list[tuple[str, str, str]] = []
    seen_rows: set[tuple[str, str, str]] = set()
    seen_names: set[str] = set()
    for line_index in range(header_index + 2, len(lines)):
        line = lines[line_index]
        if not line.strip() or "|" not in line:
            break
        cells = _markdown_cells(line)
        if len(cells) != len(header):
            findings.append(
                _warning(
                    "pesose_personnel_table_row_cells",
                    f"Personnel table line {line_index + 1} has a different "
                    "cell count from its header and needs manual review.",
                )
            )
        if len(cells) <= max(field_indexes):
            continue

        required_cells = (
            cells[field_indexes[0]],
            cells[field_indexes[1]],
            cells[field_indexes[2]],
        )

        missing = [
            PERSONNEL_COLUMNS[index]
            for index, cell in enumerate(required_cells)
            if not cell.strip()
        ]
        if missing:
            findings.append(
                _error(
                    "pesose_personnel_table_blank_cell",
                    f"Personnel table line {line_index + 1} has blank cells: "
                    + ", ".join(missing)
                    + ".",
                )
            )
            continue
        placeholders = [
            PERSONNEL_COLUMNS[index]
            for index, cell in enumerate(required_cells)
            if not _non_placeholder_text(cell)
        ]
        if placeholders:
            findings.append(
                _error(
                    "pesose_personnel_table_placeholder",
                    f"Personnel table line {line_index + 1} has placeholder "
                    "cells: " + ", ".join(placeholders) + ".",
                )
            )
            continue

        normalized = (
            _normalize_space(required_cells[0]).casefold(),
            _normalize_space(required_cells[1]).casefold(),
            _normalize_space(required_cells[2]).casefold(),
        )
        normalized_name = normalized[0]
        if normalized in seen_rows or normalized_name in seen_names:
            findings.append(
                _error(
                    "pesose_personnel_table_duplicate",
                    f"Personnel table line {line_index + 1} duplicates a "
                    "prior person or row.",
                )
            )
            continue
        seen_rows.add(normalized)
        seen_names.add(normalized_name)
        complete_rows.append(required_cells)

    if not complete_rows:
        findings.append(
            _error(
                "pesose_personnel_table_no_complete_rows",
                "The personnel table must contain at least one complete, "
                "non-placeholder data row.",
            )
        )
    if declared_roster is not None:
        findings += _reconcile_roster(complete_rows, declared_roster)
    return findings


def validate_senior_key_personnel_reconciliation(
    personnel_markdown: str | None,
    declared_roster: Sequence[object] | None,
    declared_senior_key_people: Sequence[object] | None,
    senior_key_document_manifest: Mapping[str, Mapping[str, object]] | None,
) -> list[PESOSEFinding]:
    """Reconcile PI/co-PI/Senior/Key roles to required document evidence."""
    personnel_names = _senior_key_names_from_personnel(
        personnel_markdown, declared_roster
    )
    if not personnel_names:
        return []

    declared_names = _person_name_set(declared_senior_key_people)
    manifest_names = (
        {
            _normalize_space(name).casefold()
            for name in senior_key_document_manifest
            if _non_placeholder_text(name)
        }
        if isinstance(senior_key_document_manifest, Mapping)
        else set()
    )
    missing_from_declared = sorted(personnel_names - declared_names)
    missing_from_manifest = sorted(personnel_names - manifest_names)
    if not missing_from_declared and not missing_from_manifest:
        return []

    details = []
    if missing_from_declared:
        details.append(
            "missing from senior_key.declared_people: "
            + ", ".join(missing_from_declared)
        )
    if missing_from_manifest:
        details.append(
            "missing from senior_key.documents: "
            + ", ".join(missing_from_manifest)
        )
    return [
        _error(
            "pesose_senior_key_personnel_reconciliation",
            "Every person identified as a PI, co-PI, or Senior/Key person in "
            "the personnel table or declared roster must appear in both the "
            "declared Senior/Key roster and document manifest ("
            + "; ".join(details)
            + ").",
        )
    ]


def validate_dmsp(
    markdown: str | None,
    declarations: Mapping[str, object] | None,
) -> list[PESOSEFinding]:
    """Validate Research.gov DMSP structure and explicit sharing routes."""
    products, findings = _parse_dmsp_products(markdown or "")
    if not isinstance(declarations, Mapping):
        findings.append(
            _error(
                "pesose_dmsp_declarations",
                "DMSP sharing declarations must be a mapping.",
            )
        )
        return findings

    no_products = _require_boolean(
        declarations,
        "no_data_or_research_products",
        findings,
        "pesose_dmsp_product_scope",
        "Declare no_data_or_research_products as true or false.",
    )
    if no_products is None:
        return findings

    if no_products:
        if products:
            findings.append(
                _error(
                    "pesose_dmsp_product_count",
                    "The no-product route cannot include structured product "
                    "blocks.",
                )
            )
        if not _has_substantive_no_product_justification(markdown or ""):
            findings.append(
                _error(
                    "pesose_dmsp_no_product_justification_text",
                    "The no-product route requires non-placeholder Markdown "
                    "that states a clear justification; the attestation alone "
                    "is not sufficient.",
                )
            )
        _require_true(
            declarations,
            "no_product_justification_provided",
            findings,
            "pesose_dmsp_no_product_justification",
            "The no-product route requires an explicit clear-justification "
            "attestation.",
        )
        for key in (
            "publication_supporting_data_expected",
            "publication_supporting_data_available_at_publication",
            "publication_sharing_exception_described_and_justified",
        ):
            _require_not_applicable(
                declarations,
                key,
                findings,
                "pesose_dmsp_no_product_declarations",
                f"{key} must be not_applicable on the no-product route.",
            )
        return findings

    if not 1 <= len(products) <= 4:
        findings.append(
            _error(
                "pesose_dmsp_product_count",
                "A Research.gov DMSP must describe one to four data or "
                f"research products; found {len(products)}.",
            )
        )
    _require_not_applicable(
        declarations,
        "no_product_justification_provided",
        findings,
        "pesose_dmsp_no_product_justification",
        "no_product_justification_provided must be not_applicable when "
        "products are expected.",
    )

    supporting_data = _require_boolean(
        declarations,
        "publication_supporting_data_expected",
        findings,
        "pesose_dmsp_publication_data_scope",
        "Declare publication_supporting_data_expected as true or false.",
    )
    if supporting_data is None:
        return findings
    if not supporting_data:
        for key in (
            "publication_supporting_data_available_at_publication",
            "publication_sharing_exception_described_and_justified",
        ):
            _require_not_applicable(
                declarations,
                key,
                findings,
                "pesose_dmsp_publication_availability",
                f"{key} must be not_applicable when no publication-supporting "
                "data are expected.",
            )
        return findings

    available = _require_boolean(
        declarations,
        "publication_supporting_data_available_at_publication",
        findings,
        "pesose_dmsp_publication_availability",
        "Declare whether all data supporting NSF-funded publications will be "
        "available at the time of publication.",
    )
    if available is True:
        _require_not_applicable(
            declarations,
            "publication_sharing_exception_described_and_justified",
            findings,
            "pesose_dmsp_publication_exception",
            "publication_sharing_exception_described_and_justified must be "
            "not_applicable when publication-supporting data will be shared "
            "on time.",
        )
    elif available is False:
        _require_true(
            declarations,
            "publication_sharing_exception_described_and_justified",
            findings,
            "pesose_dmsp_publication_exception",
            "Any exception to sharing publication-supporting data at the time "
            "of publication must explicitly be described and justified in "
            "the DMSP.",
        )
    return findings


def validate_manual_review_attestations(
    attestations: Mapping[str, object] | None,
) -> list[PESOSEFinding]:
    """Require human attestations; never infer substantive coverage by regex."""
    if not isinstance(attestations, Mapping):
        return [
            _error(
                "pesose_manual_review_attestations",
                "Manual-review attestations must be a mapping.",
            )
        ]

    findings: list[PESOSEFinding] = []
    for key, description in ALL_PROPOSAL_ATTESTATIONS.items():
        _require_true(
            attestations,
            key,
            findings,
            f"pesose_manual_{key}",
            f"A manual reviewer must attest {key}: true after confirming that "
            f"{description}; this validator does not infer coverage from prose.",
        )
    for key, title in TRACK_2_ACTIVITY_ATTESTATIONS.items():
        if attestations.get(key) is not True:
            findings.append(
                _warning(
                    f"pesose_manual_{key}",
                    f"A manual reviewer should attest {key}: true after "
                    f"confirming the proposal addresses {title}; this "
                    "validator does not infer coverage from prose.",
                )
            )
    return findings


def validate_tip_award_conditions(
    attestations: Mapping[str, object] | None,
) -> list[PESOSEFinding]:
    """Warn until the dynamic TIP person/entity prohibition is reviewed."""
    key = "no_prohibited_person_or_entity_will_receive_or_participate"
    if isinstance(attestations, Mapping) and attestations.get(key) is True:
        return []
    return [
        _warning(
            "pesose_award_condition_tip_person_entity_of_concern_review",
            "NSF 26-506 VII.B bars listed persons and identified entities of "
            "concern from receiving or participating in a TIP grant or "
            "activity. Manually review the current federal lists named by "
            f"that award condition and set {key}: true only after confirming "
            "the prohibition is satisfied; GrantKit does not query or cache "
            "those dynamic lists.",
        )
    ]


def _parse_dmsp_products(
    markdown: str,
) -> tuple[list[_DMSPProduct], list[PESOSEFinding]]:
    products: list[_DMSPProduct] = []
    current_product: _DMSPProduct | None = None
    current_value: list[str] | None = None
    field_lookup = {field.casefold(): field for field in DMSP_FIELDS}

    for line in markdown.splitlines():
        if _PRODUCT_HEADING_RE.match(line):
            label = re.sub(r"^\s*#{2,6}\s+", "", line).strip(" #")
            current_product = _DMSPProduct(label=label)
            products.append(current_product)
            current_value = None
            continue
        if current_product is None:
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            label = heading.group("label").strip().rstrip(":")
            official = field_lookup.get(label.casefold())
            if official is None:
                current_product.unknown_fields.append(label)
                current_value = None
            else:
                current_value = []
                current_product.fields.setdefault(official, []).append(
                    current_value
                )
            continue

        structured = _structured_dmsp_field(line, field_lookup)
        if structured is not None:
            official, label, value, explicitly_structured = structured
            if official is None:
                if explicitly_structured:
                    current_product.unknown_fields.append(label)
                    current_value = None
                elif current_value is not None:
                    current_value.append(line.strip())
                else:
                    current_product.has_unstructured_content = True
            else:
                current_value = [value] if value else []
                current_product.fields.setdefault(official, []).append(
                    current_value
                )
            continue

        if current_value is not None:
            current_value.append(line.strip())
        elif line.strip():
            current_product.has_unstructured_content = True

    findings: list[PESOSEFinding] = []
    seen_labels: set[str] = set()
    for index, product in enumerate(products, 1):
        normalized_label = _normalize_space(product.label).casefold()
        if normalized_label in seen_labels:
            findings.append(
                _error(
                    "pesose_dmsp_duplicate_product",
                    f"DMSP product heading {product.label!r} is duplicated.",
                )
            )
        seen_labels.add(normalized_label)

        if product.unknown_fields:
            findings.append(
                _warning(
                    "pesose_dmsp_unknown_field",
                    f"DMSP product {index} contains additional structured "
                    "fields outside the Research.gov set and needs manual "
                    "review: "
                    + ", ".join(sorted(set(product.unknown_fields)))
                    + ".",
                )
            )
        if product.has_unstructured_content:
            findings.append(
                _warning(
                    "pesose_dmsp_unstructured_content",
                    f"DMSP product {index} contains notes outside its eight "
                    "structured fields and needs manual review.",
                )
            )

        missing = [
            field for field in DMSP_FIELDS if field not in product.fields
        ]
        if missing:
            findings.append(
                _error(
                    "pesose_dmsp_missing_field",
                    f"DMSP product {index} is missing fields: "
                    + "; ".join(missing)
                    + ".",
                )
            )
        duplicate = [
            field
            for field, occurrences in product.fields.items()
            if len(occurrences) > 1
        ]
        if duplicate:
            findings.append(
                _error(
                    "pesose_dmsp_duplicate_field",
                    f"DMSP product {index} repeats fields: "
                    + "; ".join(duplicate)
                    + ".",
                )
            )
        blank = [
            field
            for field, occurrences in product.fields.items()
            if any(
                not _non_placeholder_text("\n".join(parts))
                for parts in occurrences
            )
        ]
        if blank:
            findings.append(
                _error(
                    "pesose_dmsp_blank_field",
                    f"DMSP product {index} has blank or placeholder fields: "
                    + "; ".join(blank)
                    + ".",
                )
            )
    return products, findings


def _structured_dmsp_field(
    line: str, field_lookup: Mapping[str, str]
) -> tuple[str | None, str, str, bool] | None:
    bold = _BOLD_FIELD_RE.match(line)
    if bold:
        label = bold.group("label").strip().rstrip(":")
        return (
            field_lookup.get(label.casefold()),
            label,
            bold.group("value").strip(),
            True,
        )

    bullet = _BULLET_FIELD_RE.match(line)
    if not bullet:
        return None
    label = bullet.group("label").strip()
    return (
        field_lookup.get(label.casefold()),
        label,
        bullet.group("value").strip(),
        False,
    )


def _has_substantive_no_product_justification(markdown: str) -> bool:
    body = "\n".join(
        line
        for line in markdown.splitlines()
        if not re.match(r"^\s*#{1,6}(?:\s|$)", line)
    ).strip()
    if not _non_placeholder_text(body):
        return False
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", body)
    return len(words) >= 5


def _find_markdown_table(
    lines: Sequence[str],
) -> tuple[int, list[str]] | None:
    for index in range(len(lines) - 1):
        header = _markdown_cells(lines[index])
        separator = _markdown_cells(lines[index + 1])
        if (
            header
            and len(header) == len(separator)
            and all(_SEPARATOR_CELL_RE.fullmatch(cell) for cell in separator)
        ):
            return index, header
    return None


def _markdown_cells(line: str) -> list[str]:
    stripped = line.strip()
    if "|" not in stripped:
        return []
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _senior_key_names_from_personnel(
    markdown: str | None, roster: Sequence[object] | None
) -> set[str]:
    names: set[str] = set()
    if not isinstance(roster, (str, bytes)) and isinstance(roster, Sequence):
        for entry in roster:
            parsed = _roster_entry(entry)
            if parsed is not None:
                name, details = parsed
                if details is not None and _is_senior_key_role(details[2]):
                    names.add(name)

    if not isinstance(markdown, str):
        return names
    lines = markdown.splitlines()
    table = _find_markdown_table(lines)
    if table is None:
        return names
    header_index, header = table
    normalized_header = tuple(
        _normalize_space(cell).casefold() for cell in header
    )
    expected_header = tuple(column.casefold() for column in PERSONNEL_COLUMNS)
    if not all(column in normalized_header for column in expected_header):
        return names
    field_indexes = tuple(
        normalized_header.index(column) for column in expected_header
    )
    for line in lines[header_index + 2 :]:
        if not line.strip() or "|" not in line:
            break
        cells = _markdown_cells(line)
        if len(cells) <= max(field_indexes):
            continue
        name = cells[field_indexes[0]]
        role = cells[field_indexes[2]]
        if _non_placeholder_text(name) and _is_senior_key_role(role):
            names.add(_normalize_space(name).casefold())
    return names


def _is_senior_key_role(role: object) -> bool:
    token = _normalize_token(role)
    if not token:
        return False
    has_pi_role = bool(re.search(r"(?:^|_)pi(?:_|$)", token)) and not bool(
        re.search(r"(?:^|_)(?:non|not)_pi(?:_|$)", token)
    )
    return bool(
        re.search(r"(?:^|_)co_pi(?:_|$)", token)
        or re.search(r"(?:^|_)copi(?:_|$)", token)
        or re.search(r"(?:^|_)principal_investigator(?:_|$)", token)
        or re.search(r"(?:^|_)co_principal_investigator(?:_|$)", token)
        or has_pi_role
        or re.search(r"(?:^|_)senior_key(?:_|$)", token)
        or re.search(r"(?:^|_)senior_personnel(?:_|$)", token)
        or re.search(r"(?:^|_)key_(?:person|personnel)(?:_|$)", token)
    )


def _person_name_set(entries: Sequence[object] | None) -> set[str]:
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        return set()
    names = set()
    for entry in entries:
        name = (
            entry.get("full_name", entry.get("Full name"))
            if isinstance(entry, Mapping)
            else entry
        )
        if _non_placeholder_text(name):
            assert isinstance(name, str)
            names.add(_normalize_space(name).casefold())
    return names


def _reconcile_roster(
    rows: Sequence[tuple[str, str, str]],
    roster: Sequence[object],
) -> list[PESOSEFinding]:
    if isinstance(roster, (str, bytes)) or not isinstance(roster, Sequence):
        return [
            _error(
                "pesose_personnel_roster",
                "declared_roster must be a sequence of names or mappings.",
            )
        ]

    findings: list[PESOSEFinding] = []
    declared: dict[str, tuple[str, str, str] | None] = {}
    for index, entry in enumerate(roster, 1):
        parsed = _roster_entry(entry)
        if parsed is None:
            findings.append(
                _error(
                    "pesose_personnel_roster",
                    f"Declared roster entry {index} must be a non-placeholder "
                    "name or a complete full_name/organizations/role mapping.",
                )
            )
            continue
        name, details = parsed
        if name in declared:
            findings.append(
                _error(
                    "pesose_personnel_roster_duplicate",
                    f"Declared roster repeats {name!r}.",
                )
            )
        declared[name] = details

    table = {
        _normalize_space(row[0]).casefold(): (
            _normalize_space(row[0]).casefold(),
            _normalize_space(row[1]).casefold(),
            _normalize_space(row[2]).casefold(),
        )
        for row in rows
    }
    missing = sorted(set(declared) - set(table))
    extra = sorted(set(table) - set(declared))
    mismatched = sorted(
        name
        for name in set(declared) & set(table)
        if declared[name] is not None and declared[name] != table[name]
    )
    if missing or extra or mismatched:
        parts = []
        if missing:
            parts.append("missing from table: " + ", ".join(missing))
        if extra:
            parts.append("not in declared roster: " + ", ".join(extra))
        if mismatched:
            parts.append(
                "organization/role mismatch: " + ", ".join(mismatched)
            )
        findings.append(
            _error(
                "pesose_personnel_roster_reconciliation",
                "Personnel table does not reconcile to the declared roster ("
                + "; ".join(parts)
                + ").",
            )
        )
    return findings


def _roster_entry(
    entry: object,
) -> tuple[str, tuple[str, str, str] | None] | None:
    if isinstance(entry, str):
        if not _non_placeholder_text(entry):
            return None
        return _normalize_space(entry).casefold(), None
    if not isinstance(entry, Mapping):
        return None

    name = entry.get("full_name", entry.get("Full name"))
    organizations = entry.get("organizations", entry.get("Organization(s)"))
    role = entry.get("role", entry.get("Role in the project"))
    values = (name, organizations, role)
    if not all(_non_placeholder_text(value) for value in values):
        return None
    normalized = (
        _normalize_space(str(values[0])).casefold(),
        _normalize_space(str(values[1])).casefold(),
        _normalize_space(str(values[2])).casefold(),
    )
    return normalized[0], normalized


def _budget_has_positive_line_b_personnel(
    budget: Mapping[str, object],
) -> bool:
    personnel = budget.get("personnel")
    if not isinstance(personnel, Mapping):
        return False
    entries = personnel.get("other")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return False
    return any(
        isinstance(entry, Mapping) and _mapping_has_positive_amount(entry)
        for entry in entries
    )


def _budget_has_subaward_entry(budget: Mapping[str, object]) -> bool:
    entries = budget.get("other_direct_costs")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return False
    return any(
        isinstance(entry, Mapping)
        and "subaward"
        in _normalize_token(entry.get("category")).replace("_", "")
        and _mapping_has_positive_amount(entry)
        for entry in entries
    )


def _mapping_has_positive_amount(item: Mapping[str, object]) -> bool:
    amount_keys = {
        "amount",
        "funding_amount",
        "funds_per_year",
        "requested_funding_amount",
        "total",
        "total_requested",
        "total_requested_salary",
    }
    return any(
        (key in amount_keys or re.fullmatch(r"year_\d+", key) is not None)
        and _is_positive_finite_number(value)
        for key, value in item.items()
        if isinstance(key, str)
    )


def _is_positive_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value > 0
    )


def _canonical_organization_type(value: object) -> str | None:
    return canonical_organization_type(value)


def canonical_organization_type(value: object) -> str | None:
    """Map accepted eligibility and budget aliases to one NSF category."""
    token = _normalize_token(value)
    return _ORGANIZATION_TYPE_ALIASES.get(token)


def _manifest_path(value: object) -> str | None:
    if not _non_placeholder_text(value):
        return None
    assert isinstance(value, str)
    normalized = posixpath.normpath(value.strip().replace("\\", "/"))
    if normalized in {"", ".", ".."}:
        return None
    if normalized.startswith("/") or normalized.startswith("../"):
        return None
    return normalized


def _require_true(
    declarations: Mapping[str, object],
    key: str,
    findings: list[PESOSEFinding],
    rule: str,
    message: str,
) -> None:
    if declarations.get(key) is not True:
        findings.append(_error(rule, message))


def _require_boolean(
    declarations: Mapping[str, object],
    key: str,
    findings: list[PESOSEFinding],
    rule: str,
    message: str,
) -> bool | None:
    value = declarations.get(key)
    if isinstance(value, bool):
        return value
    findings.append(_error(rule, message))
    return None


def _require_conditional(
    declarations: Mapping[str, object],
    key: str,
    *,
    applicable: bool,
    findings: list[PESOSEFinding],
    rule: str,
    required_message: str,
    inapplicable_message: str,
) -> None:
    value = declarations.get(key)
    if applicable:
        if value is not True:
            findings.append(_error(rule, required_message))
    elif not _is_not_applicable(value):
        findings.append(_error(rule, inapplicable_message))


def _require_scoped_boolean(
    declarations: Mapping[str, object],
    key: str,
    *,
    applicable: bool,
    findings: list[PESOSEFinding],
    rule: str,
    required_message: str,
    inapplicable_message: str,
) -> bool | None:
    if applicable:
        return _require_boolean(
            declarations, key, findings, rule, required_message
        )
    _require_not_applicable(
        declarations, key, findings, rule, inapplicable_message
    )
    return None


def _require_not_applicable(
    declarations: Mapping[str, object],
    key: str,
    findings: list[PESOSEFinding],
    rule: str,
    message: str,
) -> None:
    if not _is_not_applicable(declarations.get(key)):
        findings.append(_error(rule, message))


def _is_not_applicable(value: object) -> bool:
    return isinstance(value, str) and value.strip() == NOT_APPLICABLE


def _non_placeholder_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or _is_not_applicable(text):
        return False
    if _normalize_token(text) in {"n_a", "na", "none", "null", "dash"}:
        return False
    return _PLACEHOLDER_RE.search(text) is None


def _normalize_token(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(
        r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.casefold())
    ).strip("_")


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _one_year_before(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def _error(rule: str, message: str) -> PESOSEFinding:
    return PESOSEFinding(level="error", rule=rule, message=message)


def _warning(rule: str, message: str) -> PESOSEFinding:
    return PESOSEFinding(level="warning", rule=rule, message=message)

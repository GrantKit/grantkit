"""Focused tests for the pure PESOSE Track 2 compliance validator."""

from dataclasses import asdict

import pytest

from grantkit.funders.nsf.pesose_compliance import (
    ALL_PROPOSAL_ATTESTATIONS,
    DMSP_FIELDS,
    NOT_APPLICABLE,
    PERSONNEL_COLUMNS,
    PRIOR_SUPPORT_REVIEW_ATTESTATIONS,
    SENIOR_KEY_DOCUMENT_FIELDS,
    TRACK_2_ACTIVITY_ATTESTATIONS,
    validate_budget_scope_declarations,
    validate_dmsp,
    validate_eligibility,
    validate_letter_manifest,
    validate_manual_review_attestations,
    validate_mentoring_plan,
    validate_personnel_table,
    validate_pesose_compliance,
    validate_prior_nsf_support,
    validate_senior_key_document_manifest,
    validate_senior_key_personnel_reconciliation,
    validate_supplement_1,
    validate_tip_award_conditions,
)


def _rules(findings):
    return {finding.rule for finding in findings}


def _eligibility(
    organization_type="institution_of_higher_education",
    *,
    ihe=True,
    ownership=False,
):
    organization_label = str(organization_type).casefold()
    tribal = "tribal" in organization_label
    federal_or_ffrdc = (
        "federal" in organization_label or "ffrdc" in organization_label
    )
    nonprofit = (
        "nonprofit" in organization_label or "non-profit" in organization_label
    )
    for_profit = (
        "for-profit" in organization_label
        or "for_profit" in organization_label
    )
    return {
        "organization_type": organization_type,
        "uei_is_valid_and_active": True,
        "sam_registration_is_valid_and_active": True,
        "single_lead_organization": True,
        "has_other_nsf_funded_organizations": False,
        "all_other_nsf_funded_organizations_are_subawardees": (NOT_APPLICABLE),
        "all_subawardees_eligible": NOT_APPLICABLE,
        "has_non_nsf_supported_team_organizations": False,
        "all_non_nsf_supported_team_organizations_receive_no_nsf_support": (
            NOT_APPLICABLE
        ),
        "us_based_owned_and_controlled": (
            True if ownership else NOT_APPLICABLE
        ),
        "nonprofit_directly_associated_with_education_or_research": (
            True if nonprofit else NOT_APPLICABLE
        ),
        "for_profit_has_strong_scientific_or_engineering_capabilities": (
            True if for_profit else NOT_APPLICABLE
        ),
        "ihe_is_accredited": True if ihe else NOT_APPLICABLE,
        "ihe_has_us_campus": True if ihe else NOT_APPLICABLE,
        "all_non_exception_senior_key_have_eligible_ihe_appointments": (
            True if ihe else NOT_APPLICABLE
        ),
        "no_pi_copi_or_senior_key_has_primary_appointment_at_overseas_us_ihe_branch": (
            True if ihe else NOT_APPLICABLE
        ),
        "has_foreign_academic_senior_key_or_collaborators": (
            False if ihe else NOT_APPLICABLE
        ),
        "all_foreign_academic_experts_are_essential_and_receive_no_nsf_support": (
            NOT_APPLICABLE
        ),
        "has_senior_key_using_family_or_medical_leave_exception": (
            False if ihe else NOT_APPLICABLE
        ),
        "proposing_ihe_determined_leave_exception_senior_key_eligible": (
            NOT_APPLICABLE
        ),
        "requests_funding_for_international_branch_campus": False,
        "international_branch_benefit_and_us_campus_infeasibility_justified": (
            NOT_APPLICABLE
        ),
        "international_branch_cover_sheet_box_checked": NOT_APPLICABLE,
        "international_branch_countries": NOT_APPLICABLE,
        "pi_is_employee_of_proposing_organization": (
            NOT_APPLICABLE if ihe else True
        ),
        "pi_normally_resident_in_us": NOT_APPLICABLE if ihe else True,
        "tribal_nation_is_federally_recognized": (
            True if tribal else NOT_APPLICABLE
        ),
        "federal_ffrdc_pappg_ie2_review_completed": (
            True if federal_or_ffrdc else NOT_APPLICABLE
        ),
        "federal_ffrdc_pappg_ie2_exception_routes": (
            ["special_projects"] if federal_or_ffrdc else NOT_APPLICABLE
        ),
        "cognizant_nsf_program_officer_determined_federal_ffrdc_eligible_in_advance": (
            True if federal_or_ffrdc else NOT_APPLICABLE
        ),
        "pi_has_legal_right_to_work": True,
        "has_other_pesose_funded_proposer_employees": False,
        "all_other_pesose_funded_proposer_employees_have_legal_right_to_work": (
            NOT_APPLICABLE
        ),
    }


def _letters(count=3):
    return {
        f"letters/letter-{index}.pdf": {
            "writer_name": f"Writer {index}",
            "affiliation": f"Organization {index}",
            "project_relationship": "Independent user",
            "page_count": 2,
            "independent_current_third_party_user_or_contributor": True,
            "past_contribution": "Tested the current release.",
            "continuing_contribution": "Will test future releases.",
        }
        for index in range(1, count + 1)
    }


def _letter_page_counts(count=3):
    return {f"letters/letter-{index}.pdf": 2 for index in range(1, count + 1)}


def _no_facilities():
    return {
        "depends_on_facilities_after_award": False,
        "continuation_letter_file": NOT_APPLICABLE,
        "extent_and_term_described": NOT_APPLICABLE,
    }


def _personnel_markdown():
    return (
        "# Personnel\n\n"
        "| Full name | Organization(s) | Role in the project |\n"
        "|---|---|---|\n"
        "| Alex Example | Example University | PI |\n"
        "| Casey Contributor | Example Foundation | Collaborator |\n"
    )


def _full_personnel_markdown():
    return _personnel_markdown() + (
        "| Writer 1 | Organization 1 | Letter writer |\n"
        "| Writer 2 | Organization 2 | Letter writer |\n"
        "| Writer 3 | Organization 3 | Letter writer |\n"
    )


def _full_roster():
    return [
        {
            "full_name": "Alex Example",
            "organizations": "Example University",
            "role": "PI",
        },
        {
            "full_name": "Casey Contributor",
            "organizations": "Example Foundation",
            "role": "Collaborator",
        },
        *[
            {
                "full_name": f"Writer {index}",
                "organizations": f"Organization {index}",
                "role": "Letter writer",
            }
            for index in range(1, 4)
        ],
    ]


def _dmsp_product(index):
    lines = [f"## Product {index}"]
    for field_index, field in enumerate(DMSP_FIELDS, 1):
        lines.append(f"- **{field}:** Complete response {field_index}.")
    return "\n".join(lines)


def _dmsp_declarations():
    return {
        "no_data_or_research_products": False,
        "no_product_justification_provided": NOT_APPLICABLE,
        "publication_supporting_data_expected": True,
        "publication_supporting_data_available_at_publication": True,
        "publication_sharing_exception_described_and_justified": (
            NOT_APPLICABLE
        ),
    }


def _manual_attestations():
    return {
        key: True
        for key in (
            *ALL_PROPOSAL_ATTESTATIONS,
            *TRACK_2_ACTIVITY_ATTESTATIONS,
        )
    }


def _senior_key_manifest():
    return {
        "Alex Example": {
            "biographical_sketch_file": "senior-key/alex-biosketch.pdf",
            "current_and_pending_support_file": (
                "senior-key/alex-current-pending.pdf"
            ),
            "collaborators_and_other_affiliations_file": (
                "senior-key/alex-coa.xlsx"
            ),
            "synergistic_activities_file": ("senior-key/alex-synergistic.pdf"),
            "all_proposals_and_active_projects_disclosed": True,
            "biographical_sketch_sciencv_certified": True,
            "current_and_pending_support_sciencv_certified": True,
            "current_and_pending_support_current_accurate_complete": True,
            "coa_uses_unaltered_nsf_template": True,
            "not_a_party_to_mftrp": True,
            "synergistic_activities_page_count": 1,
            "synergistic_activities_example_count": 5,
            "research_security_training_completion_date": "2026-08-01",
            "research_security_training_within_12_months_before_submission": (
                True
            ),
            "research_security_training_evidence_reference": (
                "retained-records/alex-training-certificate.pdf"
            ),
        }
    }


def _senior_key_files():
    documents = _senior_key_manifest()["Alex Example"]
    return [documents[field] for field in SENIOR_KEY_DOCUMENT_FIELDS]


def _synergistic_page_counts():
    documents = _senior_key_manifest()["Alex Example"]
    return {documents["synergistic_activities_file"]: 1}


def _no_prior_support():
    return {
        "has_pi_or_copi_with_current_or_recent_nsf_support": False,
        "results_from_prior_nsf_support_included": NOT_APPLICABLE,
        "all_covered_pi_copi_awards_included": NOT_APPLICABLE,
        "results_from_prior_nsf_support_within_five_pages": NOT_APPLICABLE,
        **{
            key: NOT_APPLICABLE
            for key in PRIOR_SUPPORT_REVIEW_ATTESTATIONS[:-1]
        },
        "is_renewal_proposal": NOT_APPLICABLE,
        PRIOR_SUPPORT_REVIEW_ATTESTATIONS[-1]: NOT_APPLICABLE,
    }


def _no_mentoring_plan():
    return {
        "funds_postdoctoral_scholars_or_graduate_students": False,
        "unified_mentoring_plan_present": NOT_APPLICABLE,
        "mentoring_plan_page_count": NOT_APPLICABLE,
    }


def _no_mentoring_plan_evidence():
    return {"file_present": False, "page_count": NOT_APPLICABLE}


def _supplement_1_ihe():
    return {
        "proposing_organization_is_ihe": True,
        "foreign_affiliation_and_support_disclosure_documentation_maintained": (
            True
        ),
        "aor_certifies_all_senior_key_research_security_training_completed": (
            True
        ),
        "aor_certifies_all_senior_key_mftrp_certifications_complete": True,
        "aor_certifies_ihe_recr_training_plan": True,
        "ihe_maintains_confucius_institute_contract_or_agreement": False,
        "nsf_director_confucius_institute_waiver_approved": NOT_APPLICABLE,
        "dod_section_1062_waiver_requirements_fulfilled": NOT_APPLICABLE,
        "project_includes_nsf_funded_unmanned_aircraft_procurement_or_operation": (
            False
        ),
        "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems": (
            NOT_APPLICABLE
        ),
    }


def test_complete_structured_input_has_no_findings():
    findings = validate_pesose_compliance(
        proposal_submission_date="2026-08-30",
        eligibility=_eligibility(),
        letter_manifest=_letters(),
        actual_letter_files=list(_letters()),
        actual_letter_page_counts=_letter_page_counts(),
        facilities_continuation=_no_facilities(),
        personnel_markdown=_full_personnel_markdown(),
        declared_roster=_full_roster(),
        personnel_declarations={
            "roster_includes_all_required_personnel_classes": True
        },
        senior_key_document_manifest=_senior_key_manifest(),
        declared_senior_key_people=["Alex Example"],
        actual_senior_key_document_files=_senior_key_files(),
        actual_synergistic_activities_page_counts=(_synergistic_page_counts()),
        prior_nsf_support_declarations=_no_prior_support(),
        mentoring_plan_declarations=_no_mentoring_plan(),
        mentoring_plan_evidence=_no_mentoring_plan_evidence(),
        supplement_1_declarations=_supplement_1_ihe(),
        dmsp_markdown=_dmsp_product(1),
        dmsp_declarations=_dmsp_declarations(),
        manual_review_attestations=_manual_attestations(),
        award_condition_attestations={
            "no_prohibited_person_or_entity_will_receive_or_participate": True
        },
    )

    assert findings == []


def test_findings_have_only_simple_structured_fields():
    finding = validate_eligibility(None)[0]

    assert asdict(finding) == {
        "level": "error",
        "rule": "pesose_eligibility_declarations",
        "message": "PESOSE eligibility declarations must be a mapping.",
    }


@pytest.mark.parametrize(
    ("organization_type", "ihe", "ownership"),
    [
        ("IHE", True, False),
        ("non-profit", False, True),
        ("for-profit", False, True),
        ("state/local", False, False),
        ("Tribal Nation", False, False),
        ("federal agency", False, False),
        ("FFRDC", False, False),
    ],
)
def test_all_source_allowed_organization_types_are_accepted(
    organization_type, ihe, ownership
):
    declarations = _eligibility(
        organization_type, ihe=ihe, ownership=ownership
    )

    assert validate_eligibility(declarations) == []


def test_unknown_organization_type_is_a_blocker():
    declarations = _eligibility("foreign university", ihe=False)

    assert "pesose_eligibility_organization_type" in _rules(
        validate_eligibility(declarations)
    )


@pytest.mark.parametrize(
    ("key", "rule"),
    [
        ("uei_is_valid_and_active", "pesose_eligibility_active_uei"),
        (
            "sam_registration_is_valid_and_active",
            "pesose_eligibility_active_sam_registration",
        ),
        ("single_lead_organization", "pesose_eligibility_single_lead"),
        (
            "pi_has_legal_right_to_work",
            "pesose_eligibility_pi_legal_right_to_work",
        ),
    ],
)
@pytest.mark.parametrize("bad_value", [False, None, NOT_APPLICABLE])
def test_unconditional_eligibility_declarations_remain_blockers(
    key, rule, bad_value
):
    declarations = _eligibility()
    if bad_value is None:
        del declarations[key]
    else:
        declarations[key] = bad_value

    assert rule in _rules(validate_eligibility(declarations))


def test_funded_partner_declarations_follow_explicit_subaward_scope():
    declarations = _eligibility()
    declarations.update(
        {
            "has_other_nsf_funded_organizations": True,
            "all_other_nsf_funded_organizations_are_subawardees": True,
            "all_subawardees_eligible": True,
        }
    )
    assert validate_eligibility(declarations) == []

    declarations["all_subawardees_eligible"] = NOT_APPLICABLE
    assert "pesose_eligibility_subawardees" in _rules(
        validate_eligibility(declarations)
    )

    declarations = _eligibility()
    declarations["all_other_nsf_funded_organizations_are_subawardees"] = True
    assert "pesose_eligibility_subaward_structure" in _rules(
        validate_eligibility(declarations)
    )


def test_budget_line_b_cannot_contradict_funded_employee_scope():
    eligibility = _eligibility()
    budget = {
        "personnel": {
            "other": [
                {
                    "name": "Funded employee",
                    "year_1": 1,
                    "total_requested_salary": 1,
                }
            ]
        }
    }

    findings = validate_budget_scope_declarations(eligibility, budget)

    assert _rules(findings) == {
        "pesose_eligibility_funded_employee_scope_contradiction"
    }
    assert findings[0].level == "error"

    budget["personnel"]["other"][0]["year_1"] = 0
    budget["personnel"]["other"][0]["total_requested_salary"] = 0
    assert validate_budget_scope_declarations(eligibility, budget) == []


def test_subaward_entry_cannot_contradict_funded_organization_scope():
    eligibility = _eligibility()
    budget = {
        "other_direct_costs": [
            {"category": "Sub-award", "year_1": 1},
        ]
    }

    findings = validate_budget_scope_declarations(eligibility, budget)

    assert _rules(findings) == {
        "pesose_eligibility_subaward_scope_contradiction"
    }
    assert findings[0].level == "error"

    eligibility.update(
        {
            "has_other_nsf_funded_organizations": True,
            "all_other_nsf_funded_organizations_are_subawardees": True,
            "all_subawardees_eligible": True,
        }
    )
    assert validate_budget_scope_declarations(eligibility, budget) == []

    eligibility["has_other_nsf_funded_organizations"] = False
    budget["other_direct_costs"][0]["year_1"] = 0
    assert validate_budget_scope_declarations(eligibility, budget) == []


def test_non_nsf_supported_participants_are_not_forced_into_subawards():
    declarations = _eligibility()
    declarations.update(
        {
            "has_non_nsf_supported_team_organizations": True,
            "all_non_nsf_supported_team_organizations_receive_no_nsf_support": (
                True
            ),
        }
    )

    assert validate_eligibility(declarations) == []

    declarations[
        "all_non_nsf_supported_team_organizations_receive_no_nsf_support"
    ] = False
    assert "pesose_eligibility_non_nsf_participants" in _rules(
        validate_eligibility(declarations)
    )


def test_organization_specific_routes_reject_false_or_spurious_na():
    nonprofit = _eligibility("nonprofit", ihe=False, ownership=True)
    nonprofit["us_based_owned_and_controlled"] = NOT_APPLICABLE
    assert "pesose_eligibility_us_ownership_control" in _rules(
        validate_eligibility(nonprofit)
    )

    ihe = _eligibility()
    ihe["all_non_exception_senior_key_have_eligible_ihe_appointments"] = False
    assert "pesose_eligibility_ihe_appointments" in _rules(
        validate_eligibility(ihe)
    )

    ihe = _eligibility()
    ihe["ihe_is_accredited"] = False
    ihe["ihe_has_us_campus"] = False
    rules = _rules(validate_eligibility(ihe))
    assert "pesose_eligibility_ihe_accreditation" in rules
    assert "pesose_eligibility_ihe_us_campus" in rules

    ihe = _eligibility()
    ihe["pi_normally_resident_in_us"] = True
    assert "pesose_eligibility_pi_us_residency" in _rules(
        validate_eligibility(ihe)
    )


def test_ihe_foreign_academic_exception_requires_essential_unfunded_experts():
    declarations = _eligibility()
    declarations.update(
        {
            "has_foreign_academic_senior_key_or_collaborators": True,
            "all_foreign_academic_experts_are_essential_and_receive_no_nsf_support": (
                True
            ),
        }
    )

    assert validate_eligibility(declarations) == []

    declarations[
        "all_foreign_academic_experts_are_essential_and_receive_no_nsf_support"
    ] = NOT_APPLICABLE
    assert "pesose_eligibility_foreign_academic_exception" in _rules(
        validate_eligibility(declarations)
    )


def test_ihe_route_separately_prohibits_overseas_us_branch_appointments():
    declarations = _eligibility()
    key = (
        "no_pi_copi_or_senior_key_has_primary_appointment_at_"
        "overseas_us_ihe_branch"
    )
    declarations[key] = False

    finding = next(
        item
        for item in validate_eligibility(declarations)
        if item.rule
        == "pesose_eligibility_overseas_us_ihe_primary_appointment"
    )

    assert finding.level == "error"
    assert "distinct from" in finding.message

    declarations = _eligibility("nonprofit", ihe=False, ownership=True)
    declarations[key] = True
    assert "pesose_eligibility_overseas_us_ihe_primary_appointment" in _rules(
        validate_eligibility(declarations)
    )


def test_ihe_family_or_medical_leave_exception_uses_institution_determination():
    declarations = _eligibility()
    declarations.update(
        {
            "has_senior_key_using_family_or_medical_leave_exception": True,
            "proposing_ihe_determined_leave_exception_senior_key_eligible": (
                True
            ),
        }
    )

    assert validate_eligibility(declarations) == []

    declarations[
        "proposing_ihe_determined_leave_exception_senior_key_eligible"
    ] = NOT_APPLICABLE
    assert "pesose_eligibility_ihe_leave_exception_determination" in _rules(
        validate_eligibility(declarations)
    )


def test_ihe_leave_exception_scope_cannot_be_not_applicable_for_ihe():
    declarations = _eligibility()
    declarations["has_senior_key_using_family_or_medical_leave_exception"] = (
        NOT_APPLICABLE
    )

    assert "pesose_eligibility_ihe_leave_exception_scope" in _rules(
        validate_eligibility(declarations)
    )


def test_ihe_international_branch_funding_requires_both_part_justification():
    declarations = _eligibility()
    declarations.update(
        {
            "requests_funding_for_international_branch_campus": True,
            "international_branch_benefit_and_us_campus_infeasibility_justified": (
                True
            ),
            "international_branch_cover_sheet_box_checked": True,
            "international_branch_countries": ["Canada"],
        }
    )
    assert validate_eligibility(declarations) == []

    declarations[
        "international_branch_benefit_and_us_campus_infeasibility_justified"
    ] = False
    assert "pesose_eligibility_international_branch_justification" in _rules(
        validate_eligibility(declarations)
    )


def test_international_branch_scope_applies_to_non_ihe_lead_partners_too():
    declarations = _eligibility("state/local", ihe=False)
    declarations.update(
        {
            "requests_funding_for_international_branch_campus": True,
            "international_branch_benefit_and_us_campus_infeasibility_justified": (
                True
            ),
            "international_branch_cover_sheet_box_checked": True,
            "international_branch_countries": ["Canada"],
        }
    )

    assert validate_eligibility(declarations) == []


def test_nonprofit_route_requires_education_or_research_association():
    declarations = _eligibility("nonprofit", ihe=False, ownership=True)
    declarations[
        "nonprofit_directly_associated_with_education_or_research"
    ] = False

    assert "pesose_eligibility_nonprofit_activity" in _rules(
        validate_eligibility(declarations)
    )


def test_federal_ffrdc_route_requires_pappg_ie2_review():
    declarations = _eligibility("federal agency", ihe=False)
    declarations["federal_ffrdc_pappg_ie2_review_completed"] = False
    declarations["federal_ffrdc_pappg_ie2_exception_routes"] = ["invented"]
    declarations[
        "cognizant_nsf_program_officer_determined_federal_ffrdc_eligible_in_advance"
    ] = False

    rules = _rules(validate_eligibility(declarations))
    assert "pesose_eligibility_federal_ffrdc_review" in rules
    assert "pesose_eligibility_federal_ffrdc_exception_route" in rules
    assert "pesose_eligibility_federal_ffrdc_advance_determination" in rules


def test_other_funded_employee_work_authorization_is_conditional():
    declarations = _eligibility()
    declarations.update(
        {
            "has_other_pesose_funded_proposer_employees": True,
            "all_other_pesose_funded_proposer_employees_have_legal_right_to_work": True,
        }
    )
    assert validate_eligibility(declarations) == []

    declarations[
        "all_other_pesose_funded_proposer_employees_have_legal_right_to_work"
    ] = NOT_APPLICABLE
    assert "pesose_eligibility_funded_employee_work_authorization" in _rules(
        validate_eligibility(declarations)
    )


def test_senior_key_manifest_accepts_each_required_document_and_inventory():
    assert (
        validate_senior_key_document_manifest(
            _senior_key_manifest(),
            ["Alex Example"],
            _senior_key_files(),
            _synergistic_page_counts(),
            "2026-08-30",
        )
        == []
    )


@pytest.mark.parametrize("field_name", SENIOR_KEY_DOCUMENT_FIELDS)
def test_senior_key_manifest_requires_each_separate_document(field_name):
    manifest = _senior_key_manifest()
    manifest["Alex Example"][field_name] = NOT_APPLICABLE

    assert f"pesose_senior_key_{field_name}" in _rules(
        validate_senior_key_document_manifest(manifest)
    )


@pytest.mark.parametrize(
    ("key", "rule"),
    [
        (
            "all_proposals_and_active_projects_disclosed",
            "pesose_senior_key_current_pending_disclosure",
        ),
        (
            "biographical_sketch_sciencv_certified",
            "pesose_senior_key_biographical_sketch_sciencv_certified",
        ),
        (
            "current_and_pending_support_sciencv_certified",
            "pesose_senior_key_current_and_pending_support_sciencv_certified",
        ),
        (
            "current_and_pending_support_current_accurate_complete",
            "pesose_senior_key_current_and_pending_support_current_accurate_complete",
        ),
        (
            "coa_uses_unaltered_nsf_template",
            "pesose_senior_key_coa_uses_unaltered_nsf_template",
        ),
        ("not_a_party_to_mftrp", "pesose_senior_key_not_a_party_to_mftrp"),
    ],
)
def test_senior_key_manual_document_attestations_are_blockers(key, rule):
    manifest = _senior_key_manifest()
    manifest["Alex Example"][key] = False

    assert rule in _rules(validate_senior_key_document_manifest(manifest))


def test_senior_key_synergistic_activities_limits_are_enforced():
    manifest = _senior_key_manifest()
    manifest["Alex Example"]["synergistic_activities_page_count"] = 2
    manifest["Alex Example"]["synergistic_activities_example_count"] = 6

    rules = _rules(validate_senior_key_document_manifest(manifest))
    assert "pesose_senior_key_synergistic_activities_page_limit" in rules
    assert "pesose_senior_key_synergistic_activities_examples" in rules


def test_senior_key_document_formats_and_research_security_evidence():
    manifest = _senior_key_manifest()
    documents = manifest["Alex Example"]
    documents["biographical_sketch_file"] = "senior-key/alex-biosketch.txt"
    documents["research_security_training_completion_date"] = "08/01/2026"
    documents[
        "research_security_training_within_12_months_before_submission"
    ] = False
    documents["research_security_training_evidence_reference"] = "TODO"

    rules = _rules(validate_senior_key_document_manifest(manifest))
    assert "pesose_senior_key_document_format" in rules
    assert "pesose_senior_key_research_security_training_date" in rules
    assert "pesose_senior_key_research_security_training_recency" in rules
    evidence_finding = next(
        finding
        for finding in validate_senior_key_document_manifest(manifest)
        if finding.rule
        == "pesose_senior_key_research_security_training_evidence"
    )
    assert evidence_finding.level == "warning"


def test_senior_key_training_date_is_calculated_against_submission_date():
    manifest = _senior_key_manifest()
    manifest["Alex Example"][
        "research_security_training_completion_date"
    ] = "2025-08-30"
    assert (
        validate_senior_key_document_manifest(
            manifest, proposal_submission_date="2026-08-30"
        )
        == []
    )

    for invalid_date in ("2025-08-29", "2026-08-31"):
        manifest = _senior_key_manifest()
        manifest["Alex Example"][
            "research_security_training_completion_date"
        ] = invalid_date
        assert (
            "pesose_senior_key_research_security_training_recency"
            in _rules(
                validate_senior_key_document_manifest(
                    manifest, proposal_submission_date="2026-08-30"
                )
            )
        )


def test_senior_key_training_recency_requires_explicit_submission_date():
    assert "pesose_proposal_submission_date" in _rules(
        validate_senior_key_document_manifest(_senior_key_manifest())
    )


def test_senior_key_training_evidence_reference_is_optional():
    manifest = _senior_key_manifest()
    del manifest["Alex Example"][
        "research_security_training_evidence_reference"
    ]

    assert (
        validate_senior_key_document_manifest(
            manifest, proposal_submission_date="2026-08-30"
        )
        == []
    )


def test_senior_key_reconciles_actual_synergistic_pdf_page_count():
    actual_counts = _synergistic_page_counts()
    path = next(iter(actual_counts))
    actual_counts[path] = 2

    rules = _rules(
        validate_senior_key_document_manifest(
            _senior_key_manifest(),
            ["Alex Example"],
            _senior_key_files(),
            actual_counts,
            "2026-08-30",
        )
    )
    assert "pesose_senior_key_actual_synergistic_page_limit" in rules
    assert "pesose_senior_key_synergistic_page_reconciliation" in rules


def test_senior_key_manifest_reconciles_people_and_actual_files():
    findings = validate_senior_key_document_manifest(
        _senior_key_manifest(),
        ["Different Person"],
        [*_senior_key_files()[:-1], "senior-key/unmanifested.pdf"],
    )

    rules = _rules(findings)
    assert "pesose_senior_key_roster_reconciliation" in rules
    assert "pesose_senior_key_manifest_file_reconciliation" in rules


def _covered_prior_support(*, renewal=False):
    return {
        "has_pi_or_copi_with_current_or_recent_nsf_support": True,
        "results_from_prior_nsf_support_included": True,
        "all_covered_pi_copi_awards_included": True,
        "results_from_prior_nsf_support_within_five_pages": True,
        **{key: True for key in PRIOR_SUPPORT_REVIEW_ATTESTATIONS[:-1]},
        "is_renewal_proposal": renewal,
        PRIOR_SUPPORT_REVIEW_ATTESTATIONS[-1]: (
            True if renewal else NOT_APPLICABLE
        ),
    }


def test_prior_nsf_support_accepts_genuine_not_applicable_route():
    assert validate_prior_nsf_support(_no_prior_support()) == []


@pytest.mark.parametrize("key", PRIOR_SUPPORT_REVIEW_ATTESTATIONS[:-1])
def test_prior_nsf_support_requires_first_five_manual_elements(key):
    declarations = _covered_prior_support()
    declarations[key] = False

    assert f"pesose_prior_nsf_support_{key}" in _rules(
        validate_prior_nsf_support(declarations)
    )


def test_prior_nsf_support_sixth_element_is_conditional_on_renewal():
    declarations = _covered_prior_support(renewal=True)
    assert validate_prior_nsf_support(declarations) == []

    declarations["renewal_relationship_addressed"] = NOT_APPLICABLE
    assert "pesose_prior_nsf_support_renewal_relationship" in _rules(
        validate_prior_nsf_support(declarations)
    )


def test_prior_nsf_support_requires_all_covered_people_and_five_page_cap():
    declarations = _covered_prior_support()
    declarations["all_covered_pi_copi_awards_included"] = False
    declarations["results_from_prior_nsf_support_within_five_pages"] = False

    rules = _rules(validate_prior_nsf_support(declarations))
    assert "pesose_prior_nsf_support_covered_people" in rules
    assert "pesose_prior_nsf_support_page_limit" in rules


def test_prior_nsf_support_false_scope_cannot_hide_present_results():
    declarations = _no_prior_support()
    declarations["results_from_prior_nsf_support_included"] = True

    assert "pesose_prior_nsf_support_not_applicable" in _rules(
        validate_prior_nsf_support(declarations)
    )


def test_mentoring_plan_accepts_conditional_unified_one_page_plan():
    declarations = {
        "funds_postdoctoral_scholars_or_graduate_students": True,
        "unified_mentoring_plan_present": True,
        "mentoring_plan_page_count": 1,
    }
    evidence = {"file_present": True, "page_count": 1}

    assert validate_mentoring_plan(declarations, evidence) == []
    assert (
        validate_mentoring_plan(
            _no_mentoring_plan(), _no_mentoring_plan_evidence()
        )
        == []
    )


def test_mentoring_plan_missing_or_over_page_limit_is_a_blocker():
    declarations = {
        "funds_postdoctoral_scholars_or_graduate_students": True,
        "unified_mentoring_plan_present": False,
        "mentoring_plan_page_count": 2,
    }

    rules = _rules(validate_mentoring_plan(declarations))
    assert "pesose_mentoring_plan_presence" in rules
    assert "pesose_mentoring_plan_page_limit" in rules


def test_mentoring_plan_reconciles_declarations_to_actual_evidence():
    declarations = {
        "funds_postdoctoral_scholars_or_graduate_students": True,
        "unified_mentoring_plan_present": True,
        "mentoring_plan_page_count": 1,
    }
    evidence = {"file_present": False, "page_count": 2}

    rules = _rules(validate_mentoring_plan(declarations, evidence))
    assert "pesose_mentoring_plan_file_reconciliation" in rules
    assert "pesose_mentoring_plan_actual_page_limit" in rules


def test_supplement_1_accepts_ihe_without_confucius_agreement_or_drones():
    assert (
        validate_supplement_1(
            _supplement_1_ihe(),
            organization_type="institution_of_higher_education",
        )
        == []
    )


def test_supplement_1_research_security_aor_declarations_are_blockers():
    declarations = _supplement_1_ihe()
    declarations[
        "foreign_affiliation_and_support_disclosure_documentation_maintained"
    ] = False
    declarations[
        "aor_certifies_all_senior_key_research_security_training_completed"
    ] = False
    declarations[
        "aor_certifies_all_senior_key_mftrp_certifications_complete"
    ] = False
    declarations["aor_certifies_ihe_recr_training_plan"] = False

    rules = _rules(validate_supplement_1(declarations))
    assert "pesose_supplement_1_research_security_documentation" in rules
    assert "pesose_supplement_1_research_security_training_aor" in rules
    assert "pesose_supplement_1_mftrp_aor" in rules
    assert "pesose_supplement_1_ihe_recr_plan" in rules


def test_supplement_1_confucius_agreement_requires_director_waiver():
    declarations = _supplement_1_ihe()
    declarations.update(
        {
            "ihe_maintains_confucius_institute_contract_or_agreement": True,
            "nsf_director_confucius_institute_waiver_approved": True,
        }
    )
    assert validate_supplement_1(declarations) == []

    declarations["nsf_director_confucius_institute_waiver_approved"] = False
    assert "pesose_supplement_1_confucius_waiver" in _rules(
        validate_supplement_1(declarations)
    )


def test_supplement_1_confucius_agreement_accepts_dod_1062_exemption():
    declarations = _supplement_1_ihe()
    declarations.update(
        {
            "ihe_maintains_confucius_institute_contract_or_agreement": True,
            "nsf_director_confucius_institute_waiver_approved": False,
            "dod_section_1062_waiver_requirements_fulfilled": True,
        }
    )

    assert validate_supplement_1(declarations) == []


def test_supplement_1_project_drone_activity_requires_foreign_exclusion():
    declarations = _supplement_1_ihe()
    declarations.update(
        {
            "project_includes_nsf_funded_unmanned_aircraft_procurement_or_operation": (
                True
            ),
            "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems": True,
        }
    )
    assert validate_supplement_1(declarations) == []

    declarations[
        "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems"
    ] = False
    assert "pesose_supplement_1_covered_foreign_drones" in _rules(
        validate_supplement_1(declarations)
    )


def test_supplement_1_non_ihe_route_and_eligibility_reconciliation():
    declarations = {
        "proposing_organization_is_ihe": False,
        "foreign_affiliation_and_support_disclosure_documentation_maintained": (
            True
        ),
        "aor_certifies_all_senior_key_research_security_training_completed": (
            True
        ),
        "aor_certifies_all_senior_key_mftrp_certifications_complete": True,
        "aor_certifies_ihe_recr_training_plan": NOT_APPLICABLE,
        "ihe_maintains_confucius_institute_contract_or_agreement": (
            NOT_APPLICABLE
        ),
        "nsf_director_confucius_institute_waiver_approved": NOT_APPLICABLE,
        "dod_section_1062_waiver_requirements_fulfilled": NOT_APPLICABLE,
        "project_includes_nsf_funded_unmanned_aircraft_procurement_or_operation": (
            False
        ),
        "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems": (
            NOT_APPLICABLE
        ),
    }
    assert (
        validate_supplement_1(
            declarations, organization_type="state_or_local_government"
        )
        == []
    )

    assert "pesose_supplement_1_ihe_reconciliation" in _rules(
        validate_supplement_1(
            declarations, organization_type="institution_of_higher_education"
        )
    )


def test_letter_manifest_accepts_three_to_five_complete_entries():
    assert validate_letter_manifest(_letters(3), _no_facilities()) == []
    assert validate_letter_manifest(_letters(5), _no_facilities()) == []


def test_letter_manifest_reconciles_to_passed_actual_file_inventory():
    letters = _letters()
    actual_files = list(letters)
    assert (
        validate_letter_manifest(letters, _no_facilities(), actual_files) == []
    )

    actual_files[-1] = "letters/unmanifested.pdf"
    assert "pesose_letters_manifest_file_reconciliation" in _rules(
        validate_letter_manifest(letters, _no_facilities(), actual_files)
    )


def test_letter_manifest_reconciles_declared_and_actual_pdf_page_counts():
    letters = _letters()
    assert (
        validate_letter_manifest(
            letters,
            _no_facilities(),
            list(letters),
            _letter_page_counts(),
        )
        == []
    )

    actual_counts = _letter_page_counts()
    actual_counts["letters/letter-1.pdf"] = 3
    rules = _rules(
        validate_letter_manifest(
            letters, _no_facilities(), list(letters), actual_counts
        )
    )
    assert "pesose_letters_actual_page_limit" in rules
    assert "pesose_letters_page_count_reconciliation" in rules


@pytest.mark.parametrize("count", [2, 6])
def test_letter_manifest_enforces_count(count):
    assert "pesose_letters_count" in _rules(
        validate_letter_manifest(_letters(count), _no_facilities())
    )


@pytest.mark.parametrize(
    "key",
    [
        "writer_name",
        "affiliation",
        "project_relationship",
        "past_contribution",
        "continuing_contribution",
    ],
)
def test_each_letter_requires_nonplaceholder_metadata(key):
    letters = _letters()
    letters["letters/letter-1.pdf"][key] = "TODO"

    finding = next(
        item
        for item in validate_letter_manifest(letters, _no_facilities())
        if item.rule == f"pesose_letters_{key}"
    )
    expected_level = (
        "warning"
        if key in {"past_contribution", "continuing_contribution"}
        else "error"
    )
    assert finding.level == expected_level


def test_each_letter_enforces_two_page_limit():
    letters = _letters()
    letters["letters/letter-1.pdf"]["page_count"] = 3

    assert "pesose_letters_page_limit" in _rules(
        validate_letter_manifest(letters, _no_facilities())
    )


def test_each_letter_requires_independent_current_third_party_attestation():
    letters = _letters()
    letters["letters/letter-1.pdf"][
        "independent_current_third_party_user_or_contributor"
    ] = False

    assert "pesose_letters_independent_current_third_party" in _rules(
        validate_letter_manifest(letters, _no_facilities())
    )


def test_letter_manifest_rejects_duplicate_normalized_file_keys():
    letters = _letters()
    letters["letters/./letter-1.pdf"] = dict(letters["letters/letter-1.pdf"])

    assert "pesose_letters_duplicate_file" in _rules(
        validate_letter_manifest(letters, _no_facilities())
    )


def test_facilities_continuation_can_reuse_a_third_party_manifest_letter():
    facilities = {
        "depends_on_facilities_after_award": True,
        "continuation_letter_file": "letters/letter-2.pdf",
        "extent_and_term_described": True,
    }
    assert validate_letter_manifest(_letters(), facilities) == []

    facilities["continuation_letter_file"] = NOT_APPLICABLE
    facilities["extent_and_term_described"] = NOT_APPLICABLE
    findings = validate_letter_manifest(_letters(), facilities)
    rules = _rules(findings)
    assert "pesose_letters_facilities_file" in rules
    assert "pesose_letters_facilities_extent_term" in rules
    assert all(
        finding.level == "warning"
        for finding in findings
        if finding.rule.startswith("pesose_letters_facilities_")
    )


def test_proposing_organization_facilities_letter_is_separate_from_3_to_5():
    letters = _letters(5)
    facilities = {
        "depends_on_facilities_after_award": True,
        "continuation_letter_file": "letters/facilities.pdf",
        "writer_name": "Proposing Organization AOR",
        "affiliation": "Proposing Organization",
        "project_relationship": "Post-award facilities provider",
        "page_count": 1,
        "extent_and_term_described": True,
    }
    actual_files = [*letters, "letters/facilities.pdf"]
    actual_counts = {
        **_letter_page_counts(5),
        "letters/facilities.pdf": 1,
    }

    assert (
        validate_letter_manifest(
            letters,
            facilities,
            actual_files,
            actual_counts,
        )
        == []
    )


def test_facilities_not_applicable_route_is_only_for_no_dependency():
    facilities = _no_facilities()
    facilities["continuation_letter_file"] = "letters/letter-1.pdf"

    assert "pesose_letters_facilities_file" in _rules(
        validate_letter_manifest(_letters(), facilities)
    )


def test_personnel_table_accepts_exact_columns_and_name_roster():
    assert (
        validate_personnel_table(
            _personnel_markdown(),
            ["Alex Example", "Casey Contributor"],
        )
        == []
    )


def test_personnel_table_requires_exact_column_order():
    markdown = _personnel_markdown().replace(
        "Full name | Organization(s)", "Organization(s) | Full name"
    )

    finding = next(
        item
        for item in validate_personnel_table(markdown)
        if item.rule == "pesose_personnel_table_columns"
    )
    assert finding.level == "warning"


def test_personnel_table_extra_column_is_readiness_warning_not_error():
    markdown = (
        "| Full name | Organization(s) | Role in the project | Notes |\n"
        "|---|---|---|---|\n"
        "| Alex Example | Example University | PI | Complete |\n"
    )

    findings = validate_personnel_table(markdown)
    assert any(
        finding.rule == "pesose_personnel_table_columns"
        and finding.level == "warning"
        for finding in findings
    )
    assert not any(finding.level == "error" for finding in findings)


def test_non_tabular_personnel_list_requires_manual_readiness_review():
    findings = validate_personnel_table("Alex Example — University — PI")

    assert len(findings) == 1
    assert findings[0].level == "warning"
    assert findings[0].rule == "pesose_personnel_table_missing"


def test_personnel_table_rejects_blank_placeholder_and_duplicate_rows():
    markdown = (
        "| Full name | Organization(s) | Role in the project |\n"
        "|---|---|---|\n"
        "| Alex Example | Example University | PI |\n"
        "| alex example | Another Organization | Collaborator |\n"
        "| Blank Person | | Consultant |\n"
        "| TODO | Example Foundation | Advisor |\n"
    )

    rules = _rules(validate_personnel_table(markdown))
    assert "pesose_personnel_table_duplicate" in rules
    assert "pesose_personnel_table_blank_cell" in rules
    assert "pesose_personnel_table_placeholder" in rules


def test_personnel_table_requires_a_complete_nonplaceholder_row():
    markdown = (
        "| Full name | Organization(s) | Role in the project |\n"
        "|---|---|---|\n"
        "| TODO | Example University | PI |\n"
    )

    assert "pesose_personnel_table_no_complete_rows" in _rules(
        validate_personnel_table(markdown)
    )


def test_personnel_table_reconciles_names_organizations_and_roles():
    roster = [
        {
            "full_name": "Alex Example",
            "organizations": "Different University",
            "role": "PI",
        },
        "Missing Person",
    ]

    assert "pesose_personnel_roster_reconciliation" in _rules(
        validate_personnel_table(_personnel_markdown(), roster)
    )


@pytest.mark.parametrize(
    "role",
    [
        "PI",
        "co-PI",
        "PD/PI",
        "Project Director/PI",
        "Senior/Key Person",
        "Key Personnel",
    ],
)
def test_senior_key_roles_reconcile_to_declared_people_and_documents(role):
    markdown = _personnel_markdown().replace(
        "| Casey Contributor | Example Foundation | Collaborator |",
        f"| Casey Contributor | Example Foundation | {role} |",
    )
    roster = _full_roster()
    roster[1]["role"] = role

    findings = validate_senior_key_personnel_reconciliation(
        markdown,
        roster,
        ["Alex Example"],
        _senior_key_manifest(),
    )

    assert _rules(findings) == {"pesose_senior_key_personnel_reconciliation"}
    assert "casey contributor" in findings[0].message


def test_non_pi_personnel_label_is_not_treated_as_pi_role():
    markdown = _personnel_markdown().replace(
        "| Casey Contributor | Example Foundation | Collaborator |",
        "| Casey Contributor | Example Foundation | Non-PI staff |",
    )
    roster = _full_roster()
    roster[1]["role"] = "Non-PI staff"

    assert (
        validate_senior_key_personnel_reconciliation(
            markdown,
            roster,
            ["Alex Example"],
            _senior_key_manifest(),
        )
        == []
    )


@pytest.mark.parametrize("count", [1, 4])
def test_dmsp_accepts_one_to_four_products_with_exact_fields(count):
    markdown = "\n\n".join(
        _dmsp_product(index) for index in range(1, count + 1)
    )

    assert validate_dmsp(markdown, _dmsp_declarations()) == []


def test_dmsp_rejects_more_than_four_products():
    markdown = "\n\n".join(_dmsp_product(index) for index in range(1, 6))

    assert "pesose_dmsp_product_count" in _rules(
        validate_dmsp(markdown, _dmsp_declarations())
    )


def test_dmsp_reports_missing_duplicate_unknown_and_placeholder_fields():
    markdown = _dmsp_product(1)
    missing_line = "- **Public archiving:** Complete response 5."
    duplicate_line = "- **Accountability:** Duplicate response."
    markdown = markdown.replace(missing_line, "")
    markdown += "\n" + duplicate_line
    markdown += "\n- **Additional notes:** Extra structured field."
    markdown = markdown.replace(
        "- **Data availability:** Complete response 7.",
        "- **Data availability:** TODO",
    )

    findings = validate_dmsp(markdown, _dmsp_declarations())
    rules = _rules(findings)
    assert "pesose_dmsp_missing_field" in rules
    assert "pesose_dmsp_duplicate_field" in rules
    assert "pesose_dmsp_unknown_field" in rules
    assert "pesose_dmsp_blank_field" in rules
    assert (
        next(
            item
            for item in findings
            if item.rule == "pesose_dmsp_unknown_field"
        ).level
        == "warning"
    )


def test_dmsp_accepts_explicit_justified_no_product_route():
    declarations = {
        "no_data_or_research_products": True,
        "no_product_justification_provided": True,
        "publication_supporting_data_expected": NOT_APPLICABLE,
        "publication_supporting_data_available_at_publication": (
            NOT_APPLICABLE
        ),
        "publication_sharing_exception_described_and_justified": (
            NOT_APPLICABLE
        ),
    }

    justification = (
        "# DMSP\n\nNo data or research products will be created because "
        "this project only coordinates existing public artifacts."
    )
    assert validate_dmsp(justification, declarations) == []

    declarations["no_product_justification_provided"] = False
    assert "pesose_dmsp_no_product_justification" in _rules(
        validate_dmsp(justification, declarations)
    )


@pytest.mark.parametrize("markdown", ["", "# DMSP\n\nTODO", "# DMSP"])
def test_dmsp_no_product_route_requires_substantive_justification_text(
    markdown,
):
    declarations = {
        "no_data_or_research_products": True,
        "no_product_justification_provided": True,
        "publication_supporting_data_expected": NOT_APPLICABLE,
        "publication_supporting_data_available_at_publication": (
            NOT_APPLICABLE
        ),
        "publication_sharing_exception_described_and_justified": (
            NOT_APPLICABLE
        ),
    }

    assert "pesose_dmsp_no_product_justification_text" in _rules(
        validate_dmsp(markdown, declarations)
    )


def test_dmsp_no_product_declaration_cannot_hide_a_product():
    declarations = {
        "no_data_or_research_products": True,
        "no_product_justification_provided": True,
        "publication_supporting_data_expected": NOT_APPLICABLE,
        "publication_supporting_data_available_at_publication": (
            NOT_APPLICABLE
        ),
        "publication_sharing_exception_described_and_justified": (
            NOT_APPLICABLE
        ),
    }

    assert "pesose_dmsp_product_count" in _rules(
        validate_dmsp(_dmsp_product(1), declarations)
    )


def test_dmsp_publication_data_exception_must_be_explicitly_justified():
    declarations = _dmsp_declarations()
    declarations["publication_supporting_data_available_at_publication"] = (
        False
    )
    declarations["publication_sharing_exception_described_and_justified"] = (
        True
    )
    assert validate_dmsp(_dmsp_product(1), declarations) == []

    declarations["publication_sharing_exception_described_and_justified"] = (
        False
    )
    assert "pesose_dmsp_publication_exception" in _rules(
        validate_dmsp(_dmsp_product(1), declarations)
    )


def test_dmsp_no_publication_data_route_requires_not_applicable_values():
    declarations = _dmsp_declarations()
    declarations["publication_supporting_data_expected"] = False
    declarations["publication_supporting_data_available_at_publication"] = (
        NOT_APPLICABLE
    )
    assert validate_dmsp(_dmsp_product(1), declarations) == []

    declarations["publication_supporting_data_available_at_publication"] = True
    assert "pesose_dmsp_publication_availability" in _rules(
        validate_dmsp(_dmsp_product(1), declarations)
    )


def test_all_manual_content_and_track_2_attestations_are_required():
    attestations = _manual_attestations()
    assert validate_manual_review_attestations(attestations) == []

    attestations["team_qualifications"] = False
    del attestations["track2_sustainability"]
    attestations["track2_evaluation_plan"] = NOT_APPLICABLE
    rules = _rules(validate_manual_review_attestations(attestations))
    assert "pesose_manual_team_qualifications" in rules
    assert "pesose_manual_track2_sustainability" in rules
    assert "pesose_manual_track2_evaluation_plan" in rules
    assert (
        next(
            item
            for item in validate_manual_review_attestations(attestations)
            if item.rule == "pesose_manual_team_qualifications"
        ).level
        == "error"
    )
    assert all(
        item.level == "warning"
        for item in validate_manual_review_attestations(attestations)
        if item.rule.startswith("pesose_manual_track2_")
    )


def test_measure_of_success_requires_manual_review_warning():
    attestations = _manual_attestations()
    attestations["track2_measure_of_success"] = False

    finding = next(
        item
        for item in validate_manual_review_attestations(attestations)
        if item.rule == "pesose_manual_track2_measure_of_success"
    )

    assert finding.level == "warning"
    assert "at least one NSF 26-506 Measure of Success" in finding.message


def test_manual_validator_never_accepts_missing_attestations_by_inference():
    findings = validate_manual_review_attestations({})

    assert len(findings) == len(ALL_PROPOSAL_ATTESTATIONS) + len(
        TRACK_2_ACTIVITY_ATTESTATIONS
    )
    assert all(
        "does not infer coverage from prose" in item.message
        for item in findings
    )


def test_tip_person_entity_of_concern_check_stays_manual_and_nonblocking():
    findings = validate_tip_award_conditions({})

    assert len(findings) == 1
    assert findings[0].rule == (
        "pesose_award_condition_tip_person_entity_of_concern_review"
    )
    assert findings[0].level == "warning"
    assert "current federal lists" in findings[0].message
    assert "does not query or cache" in findings[0].message

    assert (
        validate_tip_award_conditions(
            {
                "no_prohibited_person_or_entity_will_receive_or_participate": (
                    True
                )
            }
        )
        == []
    )


def test_personnel_column_constant_tracks_the_exact_source_order():
    assert PERSONNEL_COLUMNS == (
        "Full name",
        "Organization(s)",
        "Role in the project",
    )

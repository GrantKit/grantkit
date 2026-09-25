"""Tests for the check runner."""

from copy import deepcopy

import pytest
import yaml

from grantkit.core.checks import CheckItem, CheckResult, run_checks
from grantkit.core.project import GrantProject
from grantkit.funders.nsf.pesose_compliance import (
    ALL_PROPOSAL_ATTESTATIONS,
    DMSP_FIELDS,
    NOT_APPLICABLE,
    PRIOR_SUPPORT_REVIEW_ATTESTATIONS,
    TRACK_2_ACTIVITY_ATTESTATIONS,
)


def _run(root):
    return run_checks(GrantProject(root))


def test_clean_project_has_no_findings(make_grant, simple_config):
    root = make_grant(
        simple_config,
        {
            "responses/summary.md": "A tidy summary of the planned work.",
            "responses/narrative.md": "A short narrative section here.",
        },
    )
    result = _run(root)
    assert result.errors == 0
    assert result.warnings == 0
    assert not result.failed()


def test_required_missing_and_empty(make_grant, simple_config):
    root = make_grant(
        simple_config,
        {"responses/summary.md": "Only the summary is written."},
    )
    result = _run(root)
    rules = {i.rule for i in result.items}
    assert "required_section_missing" in rules  # narrative file absent
    assert result.errors >= 1
    assert result.failed()


def test_word_limit_exceeded_is_error(make_grant, simple_config):
    root = make_grant(
        simple_config,
        {
            "responses/summary.md": "word " * 5,
            "responses/narrative.md": "word " * 200,  # limit is 50
        },
    )
    result = _run(root)
    over = [i for i in result.items if i.rule == "word_limit_exceeded"]
    assert len(over) == 1
    assert over[0].level == "error"
    assert over[0].section == "narrative"


def test_placeholder_is_warning(make_grant, simple_config):
    root = make_grant(
        simple_config,
        {
            "responses/summary.md": "Real content here for the summary.",
            "responses/narrative.md": "Draft. [TO BE COMPLETED]",
        },
    )
    result = _run(root)
    ph = [i for i in result.items if i.rule == "placeholder_text"]
    assert len(ph) == 1
    assert ph[0].level == "warning"


def test_unresolved_citation_error_and_resolution(make_grant, simple_config):
    responses = {
        "responses/summary.md": "We build on prior work [@known2020].",
        "responses/narrative.md": "More detail in the narrative section.",
    }
    root = make_grant(simple_config, responses)

    # No bib yet -> a warning that references.bib is missing.
    result = _run(root)
    assert any(i.rule == "missing_references_bib" for i in result.items)

    # Add a bib without the key -> unresolved error.
    (root / "references.bib").write_text(
        "@article{other2019, title={X}, author={A}, "
        "journal={J}, year={2019}}\n",
        encoding="utf-8",
    )
    result = _run(root)
    unresolved = [i for i in result.items if i.rule == "unresolved_citation"]
    assert len(unresolved) == 1
    assert unresolved[0].citation == "known2020"

    # Add the key -> resolves cleanly.
    (root / "references.bib").write_text(
        "@article{known2020, title={X}, author={A}, "
        "journal={J}, year={2020}}\n",
        encoding="utf-8",
    )
    result = _run(root)
    assert not any(i.rule == "unresolved_citation" for i in result.items)


def test_only_cited_incomplete_bibliography_entries_are_errors(
    make_grant, simple_config
):
    config = dict(simple_config)
    config["pack"] = "nsf-pappg"
    root = make_grant(
        config,
        {
            "responses/summary.md": "Evidence [@used].",
            "responses/narrative.md": "Narrative.",
        },
    )
    (root / "references.bib").write_text(
        "@article{used, title={Used}, author={A}, journal={J}, year={2026}}\n"
        "@article{unused, title={Unused}, author={B}, journal={J}, "
        "year={2026}}\n",
        encoding="utf-8",
    )

    incomplete = [
        item
        for item in _run(root).items
        if item.rule == "incomplete_bibliography_entry"
    ]

    assert incomplete
    assert {item.citation for item in incomplete} == {"used"}


def test_generic_pack_does_not_apply_nsf_bibliography_completeness(
    make_grant, simple_config
):
    root = make_grant(
        simple_config,
        {
            "responses/summary.md": "Evidence [@used].",
            "responses/narrative.md": "Narrative.",
        },
    )
    (root / "references.bib").write_text(
        "@misc{used, title={Used}, author={A}}\n",
        encoding="utf-8",
    )

    assert not any(
        item.rule == "incomplete_bibliography_entry"
        for item in _run(root).items
    )


def test_plain_text_portal_flags_markdown(make_grant, simple_config):
    config = dict(simple_config)
    config["accepts_markdown"] = False
    root = make_grant(
        config,
        {
            # Heading converts cleanly in build -> warning; table doesn't -> error.
            "responses/summary.md": "# A heading\n\n| a | b |\n|---|---|\n",
            "responses/narrative.md": "Plain text is fine here.",
        },
    )
    result = _run(root)
    md = [i for i in result.items if i.rule == "markdown_in_plain_text"]
    assert md and all(i.section == "summary" for i in md)
    assert {i.level for i in md} == {"warning", "error"}


def test_spelling_locale_warns(make_grant, simple_config):
    config = dict(simple_config)
    config["locale"] = "en-GB"
    root = make_grant(
        config,
        {
            "responses/summary.md": "We will analyze the color of policy.",
            "responses/narrative.md": "A short narrative section here.",
        },
    )
    result = _run(root)
    spelling = [i for i in result.items if i.rule == "spelling_locale"]
    words = {i.message.split("'")[1] for i in spelling}
    assert "analyze" in words or "color" in words
    assert all(i.level == "warning" for i in spelling)


def test_spelling_preserves_official_titles_in_references(
    make_grant, simple_config
):
    config = deepcopy(simple_config)
    config["locale"] = "en-US"
    config["sections"].append(
        {
            "id": "references",
            "title": "References Cited",
            "required": True,
            "file": "responses/references.md",
        }
    )
    root = make_grant(
        config,
        {
            "responses/summary.md": "A summary.",
            "responses/narrative.md": "A narrative.",
            "responses/references.md": "HMT Modelling assumptions.",
        },
    )

    spelling = [
        item for item in _run(root).items if item.rule == "spelling_locale"
    ]

    assert spelling == []


def test_budget_arithmetic_inconsistency(make_grant, simple_config):
    root = make_grant(
        simple_config,
        {
            "responses/summary.md": "Summary content here for the grant.",
            "responses/narrative.md": "Narrative content for the grant.",
        },
    )
    # Fringe stated as 10000 but rate*salary would be 0.2*100000 = 20000.
    (root / "budget.yaml").write_text(
        "years_in_budget: 1\n"
        "personnel:\n"
        "  senior_key:\n"
        "    - {name: PI, year_1: 100000}\n"
        "  other: []\n"
        "fringe_benefits: {rate: 0.2, year_1: 10000}\n"
        "indirect_costs: {rate: 0.0}\n",
        encoding="utf-8",
    )
    result = _run(root)
    assert any(i.rule == "budget_inconsistency" for i in result.items)


def test_budget_over_funder_cap(make_grant):
    # Nuffield pack carries a GBP 500,000 total cap.
    config = {
        "title": "Over budget",
        "pack": "nuffield-rda",
        "deadline": "2099-01-01",
        "sections": [
            {
                "id": "project_summary",
                "title": "Project Summary",
                "word_limit": 250,
                "required": True,
                "file": "responses/project_summary.md",
            }
        ],
    }
    root = make_grant(
        config,
        {"responses/project_summary.md": "Plain summary text here."},
    )
    (root / "budget.yaml").write_text(
        "years_in_budget: 1\n"
        "personnel:\n"
        "  senior_key:\n"
        "    - {name: PI, year_1: 600000}\n"
        "  other: []\n"
        "indirect_costs: {rate: 0.0}\n",
        encoding="utf-8",
    )
    result = _run(root)
    assert any(
        i.rule == "budget_over_total_cap" and i.level == "error"
        for i in result.items
    )


# -- NSF PESOSE Track 2 ------------------------------------------------


def _pesose_config(*, title="PESOSE: Track 2: Test", duration=24, pesose=None):
    return {
        "title": title,
        "pack": "nsf-pesose-26-506-track-2",
        "deadline": "2026-09-01",
        "duration_months": duration,
        "pesose": pesose
        or {
            "icorps_waiver_dates": "September 1-November 1, 2025",
            "icorps_track1_award": "1234567",
            "icorps_waiver_successfully_completed": True,
            "icorps_outcomes_described": True,
            "public_product_citation_key": "product",
            "public_product_open_source": True,
            "public_product_license": "Apache-2.0",
        },
        "sections": [
            {
                "id": "project_summary",
                "title": "Project Summary",
                "page_limit": 1,
                "file": "responses/project_summary.md",
            },
            {
                "id": "project_description",
                "title": "Project Description",
                "page_limit": 15,
                "file": "responses/project_description.md",
            },
            {
                "id": "references",
                "title": "References Cited",
                "file": "responses/references.md",
            },
            {
                "id": "budget_justification",
                "title": "Budget Justification",
                "page_limit": 5,
                "file": "responses/budget_justification.md",
            },
            {
                "id": "facilities_equipment_other_resources",
                "title": "Facilities, Equipment and Other Resources",
                "file": "responses/facilities_resources.md",
            },
            {
                "id": "data_management_and_sharing_plan",
                "title": "Data Management and Sharing Plan",
                "file": "responses/data_management_and_sharing_plan.md",
                "format": "fields",
            },
            {
                "id": "personnel_collaborators",
                "title": "Personnel",
                "file": "responses/personnel_collaborators.md",
            },
        ],
    }


def _pesose_responses(*, summary=None, description=None, personnel=None):
    return {
        "responses/project_summary.md": summary
        or (
            "# Overview\n\nOverview text.\n\n"
            "# Intellectual Merit\n\nMerit text.\n\n"
            "# Broader Impacts\n\nImpact text.\n\n"
            "Keywords: reproducibility; policy analysis"
        ),
        "responses/project_description.md": description
        or (
            "September 1-November 1, 2025: I-Corps for PESOSE.\n\n"
            "# Product and plan\n\nThe public product is cited [@product].\n\n"
            "# Broader Impacts\n\nThe work supports public replication."
        ),
        "responses/personnel_collaborators.md": personnel
        or (
            "| Full name | Organization(s) | Role in the project |\n"
            "|---|---|---|\n"
            "| Pat Example | Example Org | PI |\n"
        ),
        "responses/references.md": "# References Cited\n\nReference content.",
        "responses/budget_justification.md": "# Budget\n\nBudget detail.",
        "responses/facilities_resources.md": "# Facilities\n\nResources.",
        "responses/data_management_and_sharing_plan.md": (
            "# Data Management and Sharing Plan\n\nField values."
        ),
    }


def _write_pesose_bib(root, *, include_url=True):
    url = ", url={https://example.org/product}" if include_url else ""
    (root / "references.bib").write_text(
        "@misc{product, title={Public product}, "
        f"author={{{{Example Organization}}}}, year={{2026}}{url}}}\n",
        encoding="utf-8",
    )


def _compliant_pesose_budget():
    return {
        "years_in_budget": 2,
        "organization_type": "nonprofit",
        "personnel": {
            "senior_key": [
                {
                    "name": "Pat Example",
                    "title": "Principal Investigator",
                    "responsibilities": "Lead the technical work.",
                    "requested_salary_rate": 140_000,
                    "year_1": 20_000,
                    "year_2": 20_000,
                    "calendar_months": {"year_1": 1, "year_2": 1},
                    "calendar_months_reflect_requested_person_months": True,
                    "total_requested_salary": 40_000,
                    "salary_calculation_basis": "salary",
                    "budget_justification_includes_personnel_details": True,
                    "employee_of_proposing_organization": True,
                    "soc_code": "15-1252",
                    "bls_url": "https://www.bls.gov/oes/current/oes151252.htm",
                    "bls_percentile_rate": 150_000,
                    "bls_benchmark_is_non_c_level": True,
                    "soc_responsibilities_match": True,
                    "work_location": "New York, NY",
                    "bls_geographic_area": "New York-Newark-Jersey City",
                    "bls_geography_matches_work_location": True,
                    "cumulative_nsf_person_months": {
                        "year_1": 2,
                        "year_2": 2,
                    },
                }
            ],
            "other": [],
        },
        "fringe_benefits": {
            "rate": 0.2,
            "base": "salaries and wages",
            "breakdown": {"benefits": 0.2},
            "salary_escalation_rates": {"year_1": 0, "year_2": 0},
            "budget_justification_includes_fringe_details": True,
            "year_1": 4_000,
            "year_2": 4_000,
        },
        "equipment": [],
        "travel": {"domestic": [], "foreign": []},
        "participant_support": [],
        "other_direct_costs": [],
        "indirect_costs": {
            "method": "de_minimis",
            "has_current_nicra": False,
            "rate": 0.15,
            "base": "mtdc",
            "base_amount": {"year_1": 24_000, "year_2": 24_000},
            "base_amount_verified_as_mtdc": True,
        },
    }


def _write_pesose_budget(root, data):
    (root / "budget.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _write_test_pdf(path, pages=1):
    from pypdf import PdfWriter

    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as stream:
        writer.write(stream)


def _write_test_xlsx(path):
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as workbook:
        workbook.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types '
            'xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet.main+xml"/></Types>',
        )
        workbook.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.'
            "openxmlformats.org/officeDocument/2006/relationships/"
            'officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        workbook.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
            'main" xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships"><sheets><sheet name="COA" '
            'sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        workbook.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0"?><worksheet '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
            'main"><sheetData/></worksheet>',
        )


def _compliant_pesose_structural_config():
    letter_manifest = {
        f"letters/letter-{index}.pdf": {
            "writer_name": f"Writer {index}",
            "affiliation": f"Organization {index}",
            "project_relationship": "Independent current user",
            "page_count": 1,
            "independent_current_third_party_user_or_contributor": True,
            "past_contribution": "Tested the current release.",
            "continuing_contribution": "Will test future releases.",
        }
        for index in range(1, 4)
    }
    roster = [
        {
            "full_name": "Pat Example",
            "organizations": "Example Org",
            "role": "PI",
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
    senior_documents = {
        "Pat Example": {
            "biographical_sketch_file": "senior-key/pat-biosketch.pdf",
            "current_and_pending_support_file": (
                "senior-key/pat-current-pending.pdf"
            ),
            "collaborators_and_other_affiliations_file": (
                "senior-key/pat-coa.xlsx"
            ),
            "synergistic_activities_file": ("senior-key/pat-synergistic.pdf"),
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
        }
    }
    prior_support = {
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
    manual = {
        key: True
        for key in (
            *ALL_PROPOSAL_ATTESTATIONS,
            *TRACK_2_ACTIVITY_ATTESTATIONS,
        )
    }
    return {
        "proposal_submission_date": "2026-09-01",
        "pappg_conditional_requirements_reviewed": True,
        "eligibility": {
            "organization_type": "nonprofit",
            "uei_is_valid_and_active": True,
            "sam_registration_is_valid_and_active": True,
            "single_lead_organization": True,
            "has_other_nsf_funded_organizations": False,
            "all_other_nsf_funded_organizations_are_subawardees": (
                NOT_APPLICABLE
            ),
            "all_subawardees_eligible": NOT_APPLICABLE,
            "has_non_nsf_supported_team_organizations": False,
            "all_non_nsf_supported_team_organizations_receive_no_nsf_support": (
                NOT_APPLICABLE
            ),
            "us_based_owned_and_controlled": True,
            "nonprofit_directly_associated_with_education_or_research": True,
            "for_profit_has_strong_scientific_or_engineering_capabilities": (
                NOT_APPLICABLE
            ),
            "ihe_is_accredited": NOT_APPLICABLE,
            "ihe_has_us_campus": NOT_APPLICABLE,
            "all_non_exception_senior_key_have_eligible_ihe_appointments": (
                NOT_APPLICABLE
            ),
            "no_pi_copi_or_senior_key_has_primary_appointment_at_overseas_us_ihe_branch": (
                NOT_APPLICABLE
            ),
            "has_senior_key_using_family_or_medical_leave_exception": (
                NOT_APPLICABLE
            ),
            "proposing_ihe_determined_leave_exception_senior_key_eligible": (
                NOT_APPLICABLE
            ),
            "has_foreign_academic_senior_key_or_collaborators": (
                NOT_APPLICABLE
            ),
            "all_foreign_academic_experts_are_essential_and_receive_no_nsf_support": (
                NOT_APPLICABLE
            ),
            "requests_funding_for_international_branch_campus": False,
            "international_branch_benefit_and_us_campus_infeasibility_justified": (
                NOT_APPLICABLE
            ),
            "international_branch_cover_sheet_box_checked": NOT_APPLICABLE,
            "international_branch_countries": NOT_APPLICABLE,
            "pi_is_employee_of_proposing_organization": True,
            "pi_normally_resident_in_us": True,
            "tribal_nation_is_federally_recognized": NOT_APPLICABLE,
            "federal_ffrdc_pappg_ie2_review_completed": NOT_APPLICABLE,
            "federal_ffrdc_pappg_ie2_exception_routes": NOT_APPLICABLE,
            "cognizant_nsf_program_officer_determined_federal_ffrdc_eligible_in_advance": (
                NOT_APPLICABLE
            ),
            "pi_has_legal_right_to_work": True,
            "has_other_pesose_funded_proposer_employees": False,
            "all_other_pesose_funded_proposer_employees_have_legal_right_to_work": (
                NOT_APPLICABLE
            ),
        },
        "letters": {
            "manifest": letter_manifest,
            "facilities_continuation": {
                "depends_on_facilities_after_award": False,
                "continuation_letter_file": NOT_APPLICABLE,
                "extent_and_term_described": NOT_APPLICABLE,
            },
        },
        "personnel": {
            "declared_roster": roster,
            "roster_includes_all_required_personnel_classes": True,
        },
        "senior_key": {
            "declared_people": ["Pat Example"],
            "documents": senior_documents,
        },
        "prior_nsf_support": prior_support,
        "mentoring_plan": {
            "funds_postdoctoral_scholars_or_graduate_students": False,
            "unified_mentoring_plan_present": NOT_APPLICABLE,
            "mentoring_plan_page_count": NOT_APPLICABLE,
            "upload_file": NOT_APPLICABLE,
        },
        "supplement_1": {
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
            "nsf_director_confucius_institute_waiver_approved": (
                NOT_APPLICABLE
            ),
            "dod_section_1062_waiver_requirements_fulfilled": NOT_APPLICABLE,
            "project_includes_nsf_funded_unmanned_aircraft_procurement_or_operation": (
                False
            ),
            "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems": (
                NOT_APPLICABLE
            ),
        },
        "dmsp": {
            "no_data_or_research_products": False,
            "no_product_justification_provided": NOT_APPLICABLE,
            "publication_supporting_data_expected": True,
            "publication_supporting_data_available_at_publication": True,
            "publication_sharing_exception_described_and_justified": (
                NOT_APPLICABLE
            ),
        },
        "manual_review": manual,
        "award_conditions": {
            "no_prohibited_person_or_entity_will_receive_or_participate": True,
        },
    }


def _pesose_root_with_budget(
    make_grant, budget, *, responses=None, config=None
):
    root = make_grant(
        config or _pesose_config(), responses or _pesose_responses()
    )
    _write_pesose_bib(root)
    _write_pesose_budget(root, budget)
    return root


def test_pesose_structural_compliance_adapter_can_pass_end_to_end(make_grant):
    config = _pesose_config()
    config["pesose"]["compliance"] = _compliant_pesose_structural_config()
    responses = _pesose_responses(
        personnel=(
            "| Full name | Organization(s) | Role in the project |\n"
            "|---|---|---|\n"
            "| Pat Example | Example Org | PI |\n"
            "| Writer 1 | Organization 1 | Letter writer |\n"
            "| Writer 2 | Organization 2 | Letter writer |\n"
            "| Writer 3 | Organization 3 | Letter writer |\n"
        )
    )
    dmsp_lines = ["# Data Management and Sharing Plan", "", "## Product 1"]
    dmsp_lines.extend(
        f"- **{field}:** Complete response {index}."
        for index, field in enumerate(DMSP_FIELDS, 1)
    )
    responses["responses/data_management_and_sharing_plan.md"] = "\n".join(
        dmsp_lines
    )
    root = _pesose_root_with_budget(
        make_grant,
        _compliant_pesose_budget(),
        responses=responses,
        config=config,
    )

    for index in range(1, 4):
        _write_test_pdf(root / "letters" / f"letter-{index}.pdf")
    _write_test_pdf(root / "senior-key" / "pat-biosketch.pdf")
    _write_test_pdf(root / "senior-key" / "pat-current-pending.pdf")
    _write_test_pdf(root / "senior-key" / "pat-synergistic.pdf")
    coa_path = root / "senior-key" / "pat-coa.xlsx"
    _write_test_xlsx(coa_path)

    result = _run(root)
    structural_prefixes = (
        "pesose_eligibility_",
        "pesose_letters_",
        "pesose_personnel_",
        "pesose_senior_key_",
        "pesose_prior_nsf_",
        "pesose_mentoring_",
        "pesose_supplement_1_",
        "pesose_dmsp_",
        "pesose_manual_",
        "pesose_award_condition_",
        "pesose_submission_date_",
        "pesose_pappg_conditional_",
    )
    structural_findings = [
        item
        for item in result.items
        if item.rule.startswith(structural_prefixes)
    ]

    assert structural_findings == []

    import zipfile

    with zipfile.ZipFile(coa_path, "w") as workbook:
        workbook.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types '
            'xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"/>',
        )
        workbook.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
            'main"/>',
        )
    assert any(
        item.rule == "pesose_senior_key_document_unreadable"
        for item in _run(root).items
    )


def test_pesose_tip_award_condition_is_a_sourced_manual_warning(make_grant):
    config = _pesose_config()
    compliance = _compliant_pesose_structural_config()
    compliance["award_conditions"][
        "no_prohibited_person_or_entity_will_receive_or_participate"
    ] = False
    config["pesose"]["compliance"] = compliance
    root = _pesose_root_with_budget(
        make_grant, _compliant_pesose_budget(), config=config
    )

    finding = next(
        item
        for item in _run(root).items
        if item.rule
        == "pesose_award_condition_tip_person_entity_of_concern_review"
    )

    assert finding.level == "warning"
    assert finding.citation and "NSF 26-506 VII.B" in finding.citation


def test_pesose_senior_key_personnel_cannot_omit_document_manifest(
    make_grant,
):
    config = _pesose_config()
    compliance = _compliant_pesose_structural_config()
    compliance["personnel"]["declared_roster"].append(
        {
            "full_name": "Sam Senior",
            "organizations": "Example Org",
            "role": "Senior/Key Person",
        }
    )
    config["pesose"]["compliance"] = compliance
    responses = _pesose_responses(
        personnel=(
            "| Full name | Organization(s) | Role in the project |\n"
            "|---|---|---|\n"
            "| Pat Example | Example Org | PI |\n"
            "| Sam Senior | Example Org | Senior/Key Person |\n"
            "| Writer 1 | Organization 1 | Letter writer |\n"
            "| Writer 2 | Organization 2 | Letter writer |\n"
            "| Writer 3 | Organization 3 | Letter writer |\n"
        )
    )
    root = _pesose_root_with_budget(
        make_grant,
        _compliant_pesose_budget(),
        responses=responses,
        config=config,
    )

    finding = next(
        item
        for item in _run(root).items
        if item.rule == "pesose_senior_key_personnel_reconciliation"
    )

    assert finding.level == "error"
    assert "sam senior" in finding.message
    assert "senior_key.declared_people" in finding.message
    assert "senior_key.documents" in finding.message


def test_pesose_blank_submission_date_warns_on_deadline_fallback(make_grant):
    config = _pesose_config()
    compliance = _compliant_pesose_structural_config()
    compliance["proposal_submission_date"] = None
    config["pesose"]["compliance"] = compliance
    root = _pesose_root_with_budget(
        make_grant,
        _compliant_pesose_budget(),
        config=config,
    )

    findings = _run(root).items

    assert any(
        item.rule == "pesose_submission_date_uses_deadline"
        for item in findings
    )


def test_pesose_invalid_submission_date_cites_research_security_source(
    make_grant,
):
    config = _pesose_config()
    compliance = _compliant_pesose_structural_config()
    compliance["proposal_submission_date"] = "not-a-date"
    config["pesose"]["compliance"] = compliance
    root = _pesose_root_with_budget(
        make_grant,
        _compliant_pesose_budget(),
        config=config,
    )

    finding = next(
        item
        for item in _run(root).items
        if item.rule == "pesose_proposal_submission_date"
    )

    assert "Supplement 1" in finding.citation
    assert "Important Notice 149" in finding.citation


def _compliant_pesose_icorps_budget():
    budget = _compliant_pesose_budget()
    technical_lead = budget["personnel"]["senior_key"][0]
    technical_lead.update(
        {
            "id": "technical-lead-salary",
            "current_salary_rate": 140_000,
            "icorps_amount": 5_000,
            "icorps_cost_type": "technical_lead_salary",
            "icorps_role": "technical_lead",
            "icorps_salary_rate": 140_000,
            "icorps_salary_rate_no_greater_than_current": True,
        }
    )
    entrepreneurial_lead = deepcopy(technical_lead)
    entrepreneurial_lead.update(
        {
            "id": "entrepreneurial-lead-salary",
            "name": "Eli Example",
            "title": "Entrepreneurial Lead",
            "year_1": 5_000,
            "year_2": 5_000,
            "calendar_months": {"year_1": 0.5, "year_2": 0.5},
            "total_requested_salary": 10_000,
            "icorps_cost_type": "entrepreneurial_lead_salary",
            "icorps_role": "entrepreneurial_lead",
        }
    )
    budget["personnel"]["other"] = [entrepreneurial_lead]
    budget["fringe_benefits"]["year_1"] = 5_000
    budget["fringe_benefits"]["year_2"] = 5_000
    budget["indirect_costs"]["base_amount"] = {
        "year_1": 30_000,
        "year_2": 30_000,
    }
    budget["icorps_salary_support_is_sufficient"] = True
    budget["icorps_budget_justification_includes_tagged_costs"] = True
    budget["icorps_training_format_acknowledged"] = "virtual"
    budget["icorps_team"] = [
        {
            "name": "Pat Example",
            "role": "technical_lead",
            "agreed_to_program_requirements": True,
        },
        {
            "name": "Eli Example",
            "role": "entrepreneurial_lead",
            "agreed_to_program_requirements": True,
        },
        {
            "name": "Indy Mentor",
            "role": "industry_mentor",
            "agreed_to_program_requirements": True,
        },
    ]
    return budget


def test_pesose_title_and_duration_rules(make_grant):
    root = make_grant(
        _pesose_config(title="PESOSE: Track 2:Test", duration=25),
        _pesose_responses(),
    )
    _write_pesose_bib(root)
    rules = {item.rule for item in _run(root).items}
    assert "title_prefix" in rules
    assert "duration_limit_exceeded" in rules


def test_pesose_title_requires_suffix_and_duration_is_mandatory(make_grant):
    config = _pesose_config(title="PESOSE: Track 2: ")
    config.pop("duration_months")
    root = make_grant(config, _pesose_responses())
    _write_pesose_bib(root)

    findings = {item.rule: item.level for item in _run(root).items}

    assert findings["title_missing_project_name"] == "error"
    assert findings["duration_not_declared"] == "error"


def test_pesose_duration_must_be_positive_and_finite(make_grant):
    for invalid in (0, -1, float("nan"), float("inf")):
        root = make_grant(
            _pesose_config(duration=invalid), _pesose_responses()
        )
        _write_pesose_bib(root)

        assert any(
            item.rule == "duration_invalid" and item.level == "error"
            for item in _run(root).items
        )


def test_nsf_summary_and_description_headings_are_checked_in_right_files(
    make_grant,
):
    root = make_grant(
        _pesose_config(),
        _pesose_responses(
            summary=(
                "# Overview\n\nText.\n\n# Broader Impacts\n\nText.\n\n"
                "Keywords: reproducibility; policy analysis"
            ),
            description=(
                "September 1-November 1, 2025: I-Corps for PESOSE.\n\n"
                "# Broader Impacts\n\nText [@product]."
            ),
        ),
    )
    _write_pesose_bib(root)
    result = _run(root)
    rules = {item.rule for item in result.items}
    assert "nsf_summary_missing_intellectual_merit" in rules
    assert (
        next(
            item
            for item in result.items
            if item.rule == "nsf_summary_missing_intellectual_merit"
        ).level
        == "warning"
    )
    assert "nsf_missing_intellectual_merit" not in rules
    assert "nsf_description_missing_broader_impacts" not in rules


def test_base_nsf_pack_dispatches_its_content_engine(make_grant):
    config = _pesose_config(title="Example NSF proposal")
    config["pack"] = "nsf-pappg"
    config.pop("pesose")
    root = make_grant(
        config,
        _pesose_responses(
            summary="# Overview\n\nText.",
            description="# Approach\n\nText.",
        ),
    )

    rules = {item.rule for item in _run(root).items}

    assert "nsf_summary_missing_intellectual_merit" in rules
    assert "nsf_summary_missing_broader_impacts" in rules
    assert "nsf_description_missing_broader_impacts" in rules


def test_nsf_required_statements_accept_plain_and_bold_own_line_labels(
    make_grant,
):
    root = make_grant(
        _pesose_config(),
        _pesose_responses(
            summary=(
                "Overview\n\nText.\n\n**Intellectual Merit**\n\nText.\n\n"
                "Broader Impacts:\n\nText.\n\n"
                "Keywords: reproducibility; policy analysis"
            ),
            description=(
                "September 1-November 1, 2025: I-Corps for PESOSE.\n\n"
                "The public product is cited [@product].\n\n"
                "**Broader Impacts**\n\nText."
            ),
        ),
    )
    _write_pesose_bib(root)

    rules = {item.rule for item in _run(root).items}

    assert not any(rule.startswith("nsf_summary_missing_") for rule in rules)
    assert "nsf_description_missing_broader_impacts" not in rules


def test_pesose_keywords_recommend_label_and_require_two_to_five_items(
    make_grant,
):
    root = make_grant(
        _pesose_config(),
        _pesose_responses(
            summary=(
                "# Overview\n\nText.\n\n# Intellectual Merit\n\nText.\n\n"
                "# Broader Impacts\n\nText.\n\n"
                "reproducibility; policy analysis"
            )
        ),
    )
    _write_pesose_bib(root)
    keyword_items = [
        item
        for item in _run(root).items
        if item.rule.startswith("pesose_summary_keyword")
    ]
    assert [(item.rule, item.level) for item in keyword_items] == [
        ("pesose_summary_keywords_last_line", "warning")
    ]

    root = make_grant(
        _pesose_config(),
        _pesose_responses(
            summary=(
                "# Overview\n\nText.\n\n# Intellectual Merit\n\nText.\n\n"
                "# Broader Impacts\n\nText.\n\nKeywords: only-one"
            )
        ),
    )
    _write_pesose_bib(root)
    assert any(
        item.rule == "pesose_summary_keyword_count"
        for item in _run(root).items
    )


def test_pesose_icorps_waiver_dates_must_be_first_line(make_grant):
    root = make_grant(
        _pesose_config(),
        _pesose_responses(
            description=(
                "# Project Description\n\n"
                "September 1-November 1, 2025: I-Corps for PESOSE.\n\n"
                "The public product is cited [@product].\n\n"
                "# Broader Impacts\n\nText."
            )
        ),
    )
    _write_pesose_bib(root)
    assert any(
        item.rule == "pesose_icorps_dates_first_line"
        for item in _run(root).items
    )


def test_pesose_icorps_budget_cap_when_no_waiver(make_grant):
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 30_001,
            "public_product_citation_key": "product",
        }
    )
    root = make_grant(config, _pesose_responses())
    _write_pesose_bib(root)
    assert any(
        item.rule == "pesose_icorps_budget_over_cap"
        for item in _run(root).items
    )


def test_pesose_icorps_nonwaived_zero_budget_requires_manual_review(
    make_grant,
):
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 0,
            "public_product_citation_key": "product",
        }
    )
    root = make_grant(config, _pesose_responses())
    _write_pesose_bib(root)

    assert any(
        item.rule == "pesose_icorps_budget_zero_manual_review"
        and item.level == "warning"
        for item in _run(root).items
    )


def test_pesose_public_product_requires_inline_citation_and_reference_url(
    make_grant,
):
    root = make_grant(
        _pesose_config(),
        _pesose_responses(
            description=(
                "September 1-November 1, 2025: I-Corps for PESOSE.\n\n"
                "# Product and plan\n\nNo product citation here.\n\n"
                "# Broader Impacts\n\nText."
            )
        ),
    )
    _write_pesose_bib(root, include_url=False)
    rules = {item.rule for item in _run(root).items}
    assert "pesose_public_product_not_cited" in rules
    assert "pesose_public_product_reference_url_missing" in rules


def test_pesose_public_product_requires_public_url_and_license(make_grant):
    config = _pesose_config()
    config["pesose"].pop("public_product_license")
    root = make_grant(config, _pesose_responses())
    (root / "references.bib").write_text(
        "@misc{product, title={Public product}, "
        "author={{Example Organization}}, year={2026}, "
        "url={http://127.0.0.1/product}}\n",
        encoding="utf-8",
    )

    rules = {item.rule for item in _run(root).items}

    assert "pesose_public_product_license_missing" in rules
    assert "pesose_public_product_reference_url_invalid" in rules


def test_pesose_public_product_accepts_public_doi_pointer(make_grant):
    root = make_grant(_pesose_config(), _pesose_responses())
    (root / "references.bib").write_text(
        "@misc{product, title={Archived public product}, "
        "author={{Example Organization}}, year={2026}, "
        "doi={10.5281/zenodo.1234567}}\n",
        encoding="utf-8",
    )

    rules = {item.rule for item in _run(root).items}

    assert "pesose_public_product_reference_url_missing" not in rules
    assert "pesose_public_product_reference_url_invalid" not in rules


def test_pesose_public_product_rejects_resolver_url_in_doi_field(make_grant):
    root = make_grant(_pesose_config(), _pesose_responses())
    (root / "references.bib").write_text(
        "@misc{product, title={Archived public product}, "
        "author={{Example Organization}}, year={2026}, "
        "doi={https://doi.org/10.5281/zenodo.1234567}}\n",
        encoding="utf-8",
    )

    rules = {item.rule for item in _run(root).items}

    assert "pesose_public_product_reference_url_invalid" in rules


def test_pesose_zero_budget_is_not_submission_ready(make_grant):
    root = _pesose_root_with_budget(make_grant, _compliant_pesose_budget())
    budget = _compliant_pesose_budget()
    budget["personnel"]["senior_key"] = []
    budget["fringe_benefits"].update({"year_1": 0, "year_2": 0})
    budget["indirect_costs"]["base_amount"] = {"year_1": 0, "year_2": 0}
    _write_pesose_budget(root, budget)

    assert any(
        item.rule == "pesose_budget_not_finalized" and item.level == "error"
        for item in _run(root).items
    )


def test_pesose_unreadable_budget_is_a_blocker(make_grant):
    root = make_grant(_pesose_config(), _pesose_responses())
    _write_pesose_bib(root)
    (root / "budget.yaml").write_text("not: [valid\n", encoding="utf-8")

    assert any(
        item.rule == "budget_unreadable" and item.level == "error"
        for item in _run(root).items
    )


def test_pesose_personnel_table_recommends_source_column_order(make_grant):
    config = _pesose_config()
    config["pesose"]["compliance"] = {}
    root = make_grant(
        config,
        _pesose_responses(
            personnel=(
                "| Organization(s) | Full name | Role in the project |\n"
                "|---|---|---|\n"
                "| Example Org | Pat Example | PI |\n"
            )
        ),
    )
    _write_pesose_bib(root)
    assert any(
        item.rule == "pesose_personnel_table_columns"
        and item.level == "warning"
        for item in _run(root).items
    )


def test_pesose_letter_count_and_page_limits(make_grant, monkeypatch):
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    class FakePdfReader:
        def __init__(self, path):
            self.pages = [object()] * int(Path(path).read_text())

    monkeypatch.setitem(
        sys.modules, "pypdf", SimpleNamespace(PdfReader=FakePdfReader)
    )
    config = _pesose_config()
    config["pesose"]["compliance"] = _compliant_pesose_structural_config()
    root = make_grant(config, _pesose_responses())
    _write_pesose_bib(root)
    letters = root / "letters"
    letters.mkdir()
    for index, pages in enumerate((1, 2), start=1):
        (letters / f"letter-{index}.pdf").write_text(str(pages))
    result = _run(root)
    assert any(
        item.rule == "pesose_letters_manifest_file_reconciliation"
        for item in result.items
    )

    (letters / "letter-3.pdf").write_text("0")
    result = _run(root)
    assert not any(
        item.rule == "pesose_letters_manifest_file_reconciliation"
        for item in result.items
    )
    assert any(
        item.rule == "pesose_letters_actual_page_limit"
        for item in result.items
    )

    (letters / "letter-3.pdf").write_text("3")
    result = _run(root)
    assert any(
        item.rule == "pesose_letters_actual_page_limit"
        for item in result.items
    )


def test_pesose_rejects_explicit_voluntary_cost_sharing(make_grant):
    config = _pesose_config()
    config["voluntary_committed_cost_sharing"] = 1
    root = make_grant(config, _pesose_responses())
    _write_pesose_bib(root)
    assert any(
        item.rule == "pesose_voluntary_cost_sharing_prohibited"
        for item in _run(root).items
    )


def test_pack_requirements_cannot_be_omitted_or_weakened(make_grant):
    config = _pesose_config()
    config["sections"] = [
        section
        for section in config["sections"]
        if section["id"] != "data_management_and_sharing_plan"
    ]
    summary = next(
        section
        for section in config["sections"]
        if section["id"] == "project_summary"
    )
    summary["page_limit"] = 2
    description = next(
        section
        for section in config["sections"]
        if section["id"] == "project_description"
    )
    description["required"] = False

    root = make_grant(config, _pesose_responses())
    _write_pesose_bib(root)
    rules = {item.rule for item in _run(root).items}

    assert "pack_required_section_missing" in rules
    assert "pack_section_limit_weakened" in rules
    assert "pack_section_required_weakened" in rules


def test_pesose_budget_salary_employee_bls_and_month_rules(make_grant):
    budget = _compliant_pesose_budget()
    person = budget["personnel"]["senior_key"][0]
    person["employee_of_proposing_organization"] = False
    person["soc_code"] = "software developer"
    person["bls_url"] = "https://example.org/not-bls"
    person["requested_salary_rate"] = 175_000
    person["cumulative_nsf_person_months"]["year_1"] = 2.5
    root = _pesose_root_with_budget(make_grant, budget)

    rules = {item.rule for item in _run(root).items}
    assert {
        "pesose_budget_employee_only",
        "pesose_budget_soc_code",
        "pesose_budget_bls_url",
        "pesose_budget_bls_justification",
        "pesose_budget_over_two_months_justification",
    } <= rules


def test_pesose_budget_missing_cumulative_months_is_manual_review(make_grant):
    budget = _compliant_pesose_budget()
    del budget["personnel"]["senior_key"][0]["cumulative_nsf_person_months"]
    root = _pesose_root_with_budget(make_grant, budget)
    hit = next(
        item
        for item in _run(root).items
        if item.rule == "pesose_budget_nsf_months_manual_review"
    )
    assert hit.level == "warning"


def test_pesose_budget_bls_link_participates_in_url_liveness(
    make_grant, monkeypatch
):
    from grantkit.core import checks as checks_module

    budget = _compliant_pesose_budget()
    root = _pesose_root_with_budget(make_grant, budget)
    checked = []

    def fake_url_alive(url):
        checked.append(url)
        return True, "ok"

    monkeypatch.setattr(checks_module, "_url_alive", fake_url_alive)
    run_checks(GrantProject(root), check_urls=True)
    assert budget["personnel"]["senior_key"][0]["bls_url"] in checked


def test_pesose_budget_fringe_travel_and_materials_rules(make_grant):
    budget = _compliant_pesose_budget()
    del budget["fringe_benefits"]["base"]
    del budget["fringe_benefits"]["salary_escalation_rates"]
    budget["travel"]["domestic"] = [
        {
            "description": "Community interviews",
            "funds_per_year": 1_000,
        }
    ]
    budget["other_direct_costs"] = [
        {
            "category": "Materials and Supplies",
            "description": "Test hardware",
            "funding_amount": 100_000,
        }
    ]
    root = _pesose_root_with_budget(make_grant, budget)

    rules = {item.rule for item in _run(root).items}
    assert {
        "pesose_budget_fringe_fields",
        "pesose_budget_travel_breakdown",
        "pesose_budget_travel_table",
        "pesose_budget_travel_table_attestation",
        "pesose_budget_materials_justification",
    } <= rules


def test_pesose_budget_consultant_statement_and_equity_rules(make_grant):
    budget = _compliant_pesose_budget()
    budget["other_direct_costs"] = [
        {
            "category": "Consultant Services",
            "description": "Security consultant",
            "funds_per_year": 30_001,
            "payee_is_owner_or_equity_holder": True,
        }
    ]
    root = _pesose_root_with_budget(make_grant, budget)

    rules = {item.rule for item in _run(root).items}
    assert "pesose_budget_consultant_statement" in rules
    assert "pesose_budget_equity_owner_prohibited" in rules


def test_pesose_budget_accepts_complete_consultant_statement(make_grant):
    budget = _compliant_pesose_budget()
    budget["other_direct_costs"] = [
        {
            "category": "Consultant Services",
            "description": "Security consultant",
            "year_1": 25_000,
            "year_2": 25_001,
            "time_commitment": "100 hours",
            "consultant_rate": 500,
            "responsibilities": "Review the threat model.",
            "total_requested": 50_001,
            "budget_justification_includes_consultant_details": True,
            "payee_is_owner_or_equity_holder": False,
            "signed_statement": {
                "file": "other-supplementary/consultant.pdf",
                "signed": True,
                "confirms_availability": True,
                "confirms_time_commitment": True,
                "confirms_role": True,
                "confirms_rate": True,
            },
        }
    ]
    root = _pesose_root_with_budget(make_grant, budget)
    statement = root / "other-supplementary" / "consultant.pdf"
    _write_test_pdf(statement)

    rules = {item.rule for item in _run(root).items}
    assert "pesose_budget_consultant_statement" not in rules
    assert "pesose_budget_equity_owner_attestation" not in rules

    text_statement = statement.with_suffix(".txt")
    text_statement.write_text("signed", encoding="utf-8")
    budget["other_direct_costs"][0]["signed_statement"][
        "file"
    ] = "other-supplementary/consultant.txt"
    _write_pesose_budget(root, budget)
    assert any(
        item.rule == "pesose_budget_consultant_statement"
        for item in _run(root).items
    )


@pytest.mark.parametrize("category", ["Subaward", "Sub-award", "Sub award"])
def test_pesose_budget_track_2_subaward_rules(make_grant, category):
    budget = _compliant_pesose_budget()
    budget["other_direct_costs"] = [
        {
            "category": category,
            "institution": "Example University",
            "year_1": 50_000,
            "year_2": 50_000,
            "equipment": [{"description": "Server", "amount": 5_000}],
            "travel": [{}],
        }
    ]
    root = _pesose_root_with_budget(make_grant, budget)

    rules = {item.rule for item in _run(root).items}
    assert {
        "pesose_budget_equity_owner_attestation",
        "pesose_budget_subaward_ip_agreement",
        "pesose_budget_subaward_equipment_prohibited",
        "pesose_budget_subaward_justification_fields",
        "pesose_budget_subaward_pi_statement",
        "pesose_budget_subaward_budget_justification",
        "pesose_budget_subaward_co_pi_line_a",
        "pesose_budget_subaward_travel_justification",
    } <= rules


def test_pesose_budget_line_b_reconciles_to_funded_employee_scope(make_grant):
    budget = _compliant_pesose_budget()
    line_b_person = deepcopy(budget["personnel"]["senior_key"][0])
    line_b_person["name"] = "Other Funded Employee"
    budget["personnel"]["other"] = [line_b_person]
    config = _pesose_config()
    config["pesose"]["compliance"] = _compliant_pesose_structural_config()
    root = _pesose_root_with_budget(make_grant, budget, config=config)

    finding = next(
        item
        for item in _run(root).items
        if item.rule
        == "pesose_eligibility_funded_employee_scope_contradiction"
    )

    assert finding.level == "error"


def test_pesose_budget_subaward_reconciles_to_funded_org_scope(make_grant):
    budget = _compliant_pesose_budget()
    budget["other_direct_costs"] = [
        {
            "category": "Subaward",
            "institution": "Example University",
            "year_1": 1,
            "year_2": 0,
        }
    ]
    config = _pesose_config()
    config["pesose"]["compliance"] = _compliant_pesose_structural_config()
    root = _pesose_root_with_budget(make_grant, budget, config=config)

    finding = next(
        item
        for item in _run(root).items
        if item.rule == "pesose_eligibility_subaward_scope_contradiction"
    )

    assert finding.level == "error"


def test_pesose_budget_accepts_executed_subaward_ip_agreement(make_grant):
    budget = _compliant_pesose_budget()
    budget["other_direct_costs"] = [
        {
            "category": "Subaward",
            "institution": "Example University",
            "funding_amount": 100_000,
            "requested_funding_amount": 100_000,
            "purpose": "Evaluate project security.",
            "key_tasks": ["Run an independent security assessment."],
            "budget_justification_includes_subaward_details": True,
            "equipment": [],
            "payee_is_owner_or_equity_holder": False,
            "subaward_pi_statement": {
                "included_in_budget_justification": True,
                "signed_by_business_office": True,
                "confirms_willingness": True,
                "describes_responsibilities": True,
            },
            "subaward_budget_justification": {
                "file": "other-supplementary/subaward-budget.pdf",
                "follows_main_budget_format": True,
                "line_items_identified_by_letter_and_number": True,
            },
            "co_pi_listed_on_line_a": True,
            "ip_rights_agreement": {
                "file": "other-supplementary/example-ip.pdf",
                "executed": True,
            },
        }
    ]
    root = _pesose_root_with_budget(make_grant, budget)
    agreement = root / "other-supplementary" / "example-ip.pdf"
    _write_test_pdf(agreement)
    _write_test_pdf(agreement.parent / "subaward-budget.pdf")

    rules = {item.rule for item in _run(root).items}
    assert "pesose_budget_subaward_pi_statement" not in rules
    assert "pesose_budget_subaward_ip_agreement" not in rules
    assert "pesose_budget_subaward_equipment_prohibited" not in rules


def test_pesose_subaward_files_must_be_readable_pdfs_and_bj_within_five_pages(
    make_grant,
):
    budget = _compliant_pesose_budget()
    subaward = {
        "category": "Subaward",
        "institution": "Example University",
        "year_1": 50_000,
        "year_2": 50_000,
        "requested_funding_amount": 100_000,
        "purpose": "Evaluate project security.",
        "key_tasks": ["Run an independent security assessment."],
        "budget_justification_includes_subaward_details": True,
        "equipment": [],
        "payee_is_owner_or_equity_holder": False,
        "subaward_pi_statement": {
            "file": "other-supplementary/subaward-pi.pdf",
            "included_in_budget_justification": True,
            "signed_by_business_office": True,
            "confirms_willingness": True,
            "describes_responsibilities": True,
        },
        "subaward_budget_justification": {
            "file": "other-supplementary/subaward-budget.pdf",
            "follows_main_budget_format": True,
            "line_items_identified_by_letter_and_number": True,
        },
        "co_pi_listed_on_line_a": True,
        "ip_rights_agreement": {
            "file": "other-supplementary/example-ip.pdf",
            "executed": True,
        },
    }
    budget["other_direct_costs"] = [subaward]
    root = _pesose_root_with_budget(make_grant, budget)
    documents = root / "other-supplementary"
    _write_test_pdf(documents / "subaward-pi.pdf")
    _write_test_pdf(documents / "subaward-budget.pdf", pages=6)
    _write_test_pdf(documents / "example-ip.pdf")

    assert any(
        item.rule == "pesose_budget_subaward_budget_justification_page_limit"
        for item in _run(root).items
    )

    _write_test_pdf(documents / "subaward-budget.pdf")
    (documents / "subaward-pi.txt").write_text("signed", encoding="utf-8")
    (documents / "example-ip.txt").write_text("executed", encoding="utf-8")
    subaward["subaward_pi_statement"][
        "file"
    ] = "other-supplementary/subaward-pi.txt"
    subaward["ip_rights_agreement"][
        "file"
    ] = "other-supplementary/example-ip.txt"
    _write_pesose_budget(root, budget)
    rules = {item.rule for item in _run(root).items}
    assert "pesose_budget_subaward_pi_statement" in rules
    assert "pesose_budget_subaward_ip_agreement" in rules


def test_pesose_budget_indirect_cost_routes(make_grant):
    budget = _compliant_pesose_budget()
    budget["indirect_costs"] = {
        "method": "de_minimis",
        "has_current_nicra": True,
        "rate": 0.1,
        "base": "total_direct_costs",
    }
    root = _pesose_root_with_budget(make_grant, budget)
    rules = {item.rule for item in _run(root).items}
    assert {
        "pesose_budget_de_minimis_nicra_attestation",
        "pesose_budget_de_minimis_rate",
        "pesose_budget_de_minimis_base",
    } <= rules

    budget["indirect_costs"] = {
        "method": "nicra",
        "rate": 0.2,
        "has_current_nicra": True,
    }
    _write_pesose_budget(root, budget)
    assert any(
        item.rule == "pesose_budget_nicra_attestation"
        for item in _run(root).items
    )


def test_pesose_budget_complete_evidence_is_clean(make_grant):
    root = _pesose_root_with_budget(make_grant, _compliant_pesose_budget())
    budget_rules = {
        item.rule
        for item in _run(root).items
        if item.rule.startswith("pesose_budget_")
    }
    assert budget_rules == set()


def test_pesose_budget_organization_type_matches_eligibility(make_grant):
    budget = _compliant_pesose_budget()
    budget["organization_type"] = "federal_agency"
    config = _pesose_config()
    config["pesose"]["compliance"] = _compliant_pesose_structural_config()
    root = _pesose_root_with_budget(make_grant, budget, config=config)

    assert any(
        item.rule == "pesose_budget_organization_type_mismatch"
        and item.level == "error"
        for item in _run(root).items
    )


def test_pesose_budget_does_not_close_organization_eligibility(make_grant):
    for organization_type in ("tribal_nation", "federal_agency", "ffrdc"):
        budget = _compliant_pesose_budget()
        budget["organization_type"] = organization_type
        root = _pesose_root_with_budget(make_grant, budget)
        rules = {item.rule for item in _run(root).items}
        assert "pesose_budget_organization_type_invalid" not in rules


def test_pesose_budget_ihe_state_local_salary_routes(make_grant):
    budget = _compliant_pesose_budget()
    budget["organization_type"] = "higher_education"
    person = budget["personnel"]["senior_key"][0]
    person["employment_status"] = "existing"
    root = _pesose_root_with_budget(make_grant, budget)
    findings = _run(root).items
    rules = {item.rule for item in findings}
    assert "pesose_budget_existing_employee_salary_statement" in rules
    assert "pesose_budget_existing_employee_rate" not in rules
    assert (
        next(
            item
            for item in findings
            if item.rule == "pesose_budget_existing_employee_salary_statement"
        ).level
        == "warning"
    )

    person["requested_rate_no_greater_than_current_attestation"] = False
    _write_pesose_budget(root, budget)
    assert any(
        item.rule == "pesose_budget_existing_employee_rate"
        and item.level == "error"
        for item in _run(root).items
    )

    person["requested_rate_no_greater_than_current_attestation"] = True
    person["anticipated_institutional_escalation_rates"] = {
        "year_1": 0.03,
        "year_2": 0.03,
    }
    _write_pesose_budget(root, budget)
    assert not any(
        item.rule == "pesose_budget_existing_employee_salary_statement"
        for item in _run(root).items
    )

    person["employment_status"] = "new"
    _write_pesose_budget(root, budget)
    assert any(
        item.rule == "pesose_budget_new_employee_written_policy"
        for item in _run(root).items
    )

    person["salary_rate_consistent_with_written_policy"] = True
    person["escalation_rates_consistent_with_written_policy"] = True
    _write_pesose_budget(root, budget)
    assert not any(
        item.rule == "pesose_budget_new_employee_written_policy"
        for item in _run(root).items
    )


def test_pesose_budget_personnel_fields_calendar_months_and_hourly_basis(
    make_grant,
):
    budget = _compliant_pesose_budget()
    person = budget["personnel"]["senior_key"][0]
    for field in (
        "title",
        "responsibilities",
        "calendar_months",
        "total_requested_salary",
    ):
        del person[field]
    person["salary_calculation_basis"] = "hourly"
    person["hours_per_month"] = 160
    root = _pesose_root_with_budget(make_grant, budget)
    rules = {item.rule for item in _run(root).items}
    assert "pesose_budget_personnel_justification_fields" in rules
    assert "pesose_budget_173_33_hours" in rules


def test_pesose_budget_bls_benchmark_matches_duties_and_geography(make_grant):
    budget = _compliant_pesose_budget()
    person = budget["personnel"]["senior_key"][0]
    person["bls_benchmark_is_non_c_level"] = False
    person["soc_responsibilities_match"] = False
    person["bls_geography_matches_work_location"] = False
    root = _pesose_root_with_budget(make_grant, budget)
    assert any(
        item.rule == "pesose_budget_bls_match_attestations"
        for item in _run(root).items
    )


def test_pesose_budget_equipment_and_travel_justification(make_grant):
    budget = _compliant_pesose_budget()
    budget["equipment"] = [
        {"description": "Build server", "funding_amount": 5_000}
    ]
    budget["travel"]["domestic"] = [
        {
            "description": "Contributor interviews",
            "funds_per_year": 1_000,
            "breakdown": {"airfare": 700, "lodging": 300},
            "cost_rule": "48_cfr_31_205_46",
        }
    ]
    budget["budget_justification_attestations"] = {
        "travel_breakdown_covers_each_trip": True
    }
    responses = _pesose_responses()
    responses["responses/budget_justification.md"] = (
        "# Budget\n\n| Trip | Airfare | Lodging |\n"
        "|---|---:|---:|\n| Interviews | 700 | 300 |\n"
    )
    root = _pesose_root_with_budget(make_grant, budget, responses=responses)
    findings = _run(root).items
    rules = {item.rule for item in findings}
    assert "pesose_budget_equipment_necessity" in rules
    assert (
        next(
            item
            for item in findings
            if item.rule == "pesose_budget_equipment_justification_attestation"
        ).level
        == "warning"
    )
    assert "pesose_budget_travel_justification" in rules
    assert "pesose_budget_travel_cost_rule" in rules


def test_pesose_budget_zero_declared_total_cannot_hide_funded_years(
    make_grant,
):
    budget = _compliant_pesose_budget()
    budget["equipment"] = [{"funding_amount": 0, "year_1": 5_000, "year_2": 0}]
    budget["travel"]["domestic"] = [
        {"funding_amount": 0, "year_1": 1_000, "year_2": 0}
    ]
    root = _pesose_root_with_budget(make_grant, budget)
    rules = {item.rule for item in _run(root).items}
    assert {
        "pesose_budget_equipment_necessity",
        "pesose_budget_travel_justification",
        "pesose_budget_line_total_mismatch",
    } <= rules


def test_pesose_budget_consultant_fields_and_line_g_services(make_grant):
    budget = _compliant_pesose_budget()
    budget["other_direct_costs"] = [
        {
            "category": "Consultant Services",
            "description": "Security consultant",
            "funding_amount": 10_000,
            "payee_is_owner_or_equity_holder": False,
        },
        {
            "category": "Other",
            "description": "Fee-for-service testing",
            "funding_amount": 5_000,
        },
    ]
    root = _pesose_root_with_budget(make_grant, budget)
    rules = {item.rule for item in _run(root).items}
    assert "pesose_budget_consultant_justification_fields" in rules
    assert "pesose_budget_line_g_services_description" in rules


def test_pesose_icorps_actual_budget_team_and_allowed_costs(make_grant):
    budget = _compliant_pesose_icorps_budget()
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 10_000,
            "public_product_citation_key": "product",
        }
    )
    root = _pesose_root_with_budget(make_grant, budget, config=config)
    rules = {
        item.rule
        for item in _run(root).items
        if item.rule.startswith("pesose_icorps_")
    }
    assert rules == set()


def test_pesose_icorps_rejects_prohibited_and_unlinked_costs(make_grant):
    budget = _compliant_pesose_icorps_budget()
    technical_lead = budget["personnel"]["senior_key"][0]
    technical_lead["icorps_amount"] = 25_000
    technical_lead["icorps_salary_rate"] = 200_000
    technical_lead["icorps_salary_rate_no_greater_than_current"] = False
    budget["personnel"]["other"] = []
    budget["other_direct_costs"] = [
        {
            "id": "marketing",
            "category": "I-Corps outreach",
            "funds_per_year": 500,
            "icorps_amount": 1_000,
            "icorps_cost_type": "marketing",
        }
    ]
    budget["travel"]["foreign"] = [
        {
            "id": "foreign-interviews",
            "description": "International interviews",
            "necessity": "Interview contributors.",
            "funds_per_year": 3_000,
            "breakdown": {"airfare": 3_000},
            "cost_rule": "2_cfr_200_475",
            "icorps_amount": 6_000,
            "icorps_cost_type": "international_travel",
        }
    ]
    budget["icorps_team"] = [
        {
            "name": "Pat Example",
            "role": "technical_lead",
            "agreed_to_program_requirements": False,
        }
    ]
    budget["budget_justification_attestations"] = {
        "travel_breakdown_covers_each_trip": True
    }
    responses = _pesose_responses()
    responses["responses/budget_justification.md"] = (
        "# Budget\n\n| Trip | Airfare |\n|---|---:|\n| Interviews | 3000 |\n"
    )
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 30_000,
            "public_product_citation_key": "product",
        }
    )
    root = _pesose_root_with_budget(
        make_grant, budget, responses=responses, config=config
    )
    rules = {item.rule for item in _run(root).items}
    assert {
        "pesose_icorps_cost_prohibited",
        "pesose_icorps_international_travel_prohibited",
        "pesose_icorps_salary_rate",
        "pesose_icorps_actual_budget_over_cap",
        "pesose_icorps_budget_link_mismatch",
        "pesose_icorps_team_agreement_manual_review",
        "pesose_icorps_team_roles_manual_review",
    } <= rules


def test_pesose_budget_period_and_cumulative_month_keys(make_grant):
    budget = _compliant_pesose_budget()
    budget["years_in_budget"] = 3
    person = budget["personnel"]["senior_key"][0]
    person["calendar_months"]["year_3"] = 0
    person["cumulative_nsf_person_months"]["year_3"] = 0
    budget["indirect_costs"]["base_amount"]["year_3"] = 0
    root = _pesose_root_with_budget(make_grant, budget)
    assert any(
        item.rule == "pesose_budget_years_exceeded"
        for item in _run(root).items
    )

    budget = _compliant_pesose_budget()
    budget["personnel"]["senior_key"][0]["cumulative_nsf_person_months"] = {
        "foo": 0
    }
    _write_pesose_budget(root, budget)
    assert any(
        item.rule == "pesose_budget_nsf_months_invalid"
        for item in _run(root).items
    )


def test_pesose_budget_calendar_months_reconcile_when_rates_are_provided(
    make_grant,
):
    budget = _compliant_pesose_budget()
    person = budget["personnel"]["senior_key"][0]
    person["annual_salary_rate_by_year"] = {
        "year_1": 240_000,
        "year_2": 240_000,
    }
    root = _pesose_root_with_budget(make_grant, budget)
    assert not any(
        item.rule == "pesose_budget_calendar_months_mismatch"
        for item in _run(root).items
    )

    person["calendar_months"]["year_2"] = 0.5
    _write_pesose_budget(root, budget)
    finding = next(
        item
        for item in _run(root).items
        if item.rule == "pesose_budget_calendar_months_mismatch"
    )
    assert finding.level == "warning"


def test_pesose_budget_evidence_must_be_tied_to_justification(make_grant):
    budget = _compliant_pesose_budget()
    person = budget["personnel"]["senior_key"][0]
    person["budget_justification_includes_personnel_details"] = False
    person["calendar_months_reflect_requested_person_months"] = False
    budget["fringe_benefits"][
        "budget_justification_includes_fringe_details"
    ] = False
    root = _pesose_root_with_budget(make_grant, budget)
    findings = _run(root).items
    rules = {item.rule for item in findings}
    assert {
        "pesose_budget_personnel_justification_attestation",
        "pesose_budget_calendar_months_attestation",
        "pesose_budget_fringe_justification_attestation",
    } <= rules
    assert (
        next(
            item
            for item in findings
            if item.rule == "pesose_budget_calendar_months_attestation"
        ).level
        == "warning"
    )


def test_pesose_budget_requires_verified_indirect_base(make_grant):
    budget = _compliant_pesose_budget()
    del budget["indirect_costs"]["base_amount"]
    del budget["indirect_costs"]["base_amount_verified_as_mtdc"]
    root = _pesose_root_with_budget(make_grant, budget)
    rules = {item.rule for item in _run(root).items}
    assert {
        "pesose_budget_indirect_base_amount",
        "pesose_budget_indirect_base_attestation",
    } <= rules


def test_pesose_budget_negative_amount_cannot_bypass_cap(make_grant):
    budget = _compliant_pesose_budget()
    person = budget["personnel"]["senior_key"][0]
    person.update(
        {
            "year_1": 1_600_000,
            "year_2": -200_000,
            "total_requested_salary": 1_400_000,
            "requested_salary_rate": 1_600_000,
            "bls_percentile_rate": 2_000_000,
        }
    )
    budget["indirect_costs"]["base_amount"] = {"year_1": 0, "year_2": 0}
    root = _pesose_root_with_budget(make_grant, budget)
    rules = {item.rule for item in _run(root).items}
    assert "budget_over_total_cap" not in rules
    assert "pesose_budget_amount_nonnegative" in rules

    person["year_2"] = True
    person["total_requested_salary"] = 1_600_001
    _write_pesose_budget(root, budget)
    assert any(
        item.rule == "pesose_budget_amount_nonnegative"
        for item in _run(root).items
    )


def test_pesose_icorps_requires_positive_actual_and_salary_support(make_grant):
    budget = _compliant_pesose_icorps_budget()
    for person in (
        budget["personnel"]["senior_key"] + budget["personnel"]["other"]
    ):
        for key in (
            "icorps_amount",
            "icorps_cost_type",
            "icorps_role",
            "icorps_salary_rate",
            "icorps_salary_rate_no_greater_than_current",
        ):
            person.pop(key, None)
    budget["icorps_salary_support_is_sufficient"] = False
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 0,
            "public_product_citation_key": "product",
        }
    )
    root = _pesose_root_with_budget(make_grant, budget, config=config)
    items = _run(root).items
    rules = {item.rule for item in items}
    assert {
        "pesose_icorps_actual_budget_missing",
        "pesose_icorps_salary_support_missing",
    } <= rules
    levels = {item.rule: item.level for item in items}
    assert levels["pesose_icorps_actual_budget_missing"] == "warning"
    assert levels["pesose_icorps_salary_support_missing"] == "warning"
    assert levels["pesose_icorps_salary_support_attestation"] == "warning"


def test_pesose_icorps_does_not_require_both_salary_roles_to_be_linked(
    make_grant,
):
    budget = _compliant_pesose_icorps_budget()
    entrepreneurial_lead = budget["personnel"]["other"][0]
    for key in (
        "icorps_amount",
        "icorps_cost_type",
        "icorps_role",
        "icorps_salary_rate",
        "icorps_salary_rate_no_greater_than_current",
    ):
        entrepreneurial_lead.pop(key, None)
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 5_000,
            "public_product_citation_key": "product",
        }
    )
    root = _pesose_root_with_budget(make_grant, budget, config=config)
    rules = {item.rule for item in _run(root).items}
    assert "pesose_icorps_salary_support_missing" not in rules
    assert "pesose_icorps_team_roles_manual_review" not in rules
    assert "pesose_icorps_budget_link_mismatch" not in rules


def test_pesose_icorps_nonsalary_item_cannot_satisfy_salary_support(
    make_grant,
):
    budget = _compliant_pesose_icorps_budget()
    for person in (
        budget["personnel"]["senior_key"] + budget["personnel"]["other"]
    ):
        for key in (
            "icorps_amount",
            "icorps_cost_type",
            "icorps_role",
            "icorps_salary_rate",
            "icorps_salary_rate_no_greater_than_current",
        ):
            person.pop(key, None)
    budget["equipment"] = [
        {
            "id": "headset",
            "description": "Training headset",
            "necessity": "Participate in virtual training.",
            "budget_justification_includes_description_and_necessity": True,
            "year_1": 10_000,
            "year_2": 0,
            "icorps_amount": 10_000,
            "icorps_cost_type": "headset",
            "icorps_role": "technical_lead",
            "current_salary_rate": 140_000,
            "icorps_salary_rate": 140_000,
            "icorps_salary_rate_no_greater_than_current": True,
        }
    ]
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 10_000,
            "public_product_citation_key": "product",
        }
    )
    root = _pesose_root_with_budget(make_grant, budget, config=config)
    rules = {item.rule for item in _run(root).items}
    assert "pesose_icorps_salary_support_missing" in rules


def test_pesose_icorps_salary_tags_outside_lines_ab_do_not_count(
    make_grant,
):
    budget = _compliant_pesose_icorps_budget()
    for person in (
        budget["personnel"]["senior_key"] + budget["personnel"]["other"]
    ):
        for key in (
            "icorps_amount",
            "icorps_cost_type",
            "icorps_role",
            "icorps_salary_rate",
            "icorps_salary_rate_no_greater_than_current",
        ):
            person.pop(key, None)
    budget["equipment"] = [
        {
            "id": "misclassified-tl-salary",
            "description": "Training equipment",
            "necessity": "Participate in virtual training.",
            "budget_justification_includes_description_and_necessity": True,
            "year_1": 5_000,
            "year_2": 0,
            "icorps_amount": 5_000,
            "icorps_cost_type": "technical_lead_salary",
            "icorps_role": "technical_lead",
            "current_salary_rate": 140_000,
            "icorps_salary_rate": 140_000,
            "icorps_salary_rate_no_greater_than_current": True,
        }
    ]
    budget["other_direct_costs"] = [
        {
            "id": "misclassified-el-salary",
            "category": "Other",
            "description": "Training services",
            "year_1": 5_000,
            "year_2": 0,
            "icorps_amount": 5_000,
            "icorps_cost_type": "entrepreneurial_lead_salary",
            "icorps_role": "entrepreneurial_lead",
            "current_salary_rate": 140_000,
            "icorps_salary_rate": 140_000,
            "icorps_salary_rate_no_greater_than_current": True,
        }
    ]
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 10_000,
            "public_product_citation_key": "product",
        }
    )
    root = _pesose_root_with_budget(make_grant, budget, config=config)
    findings = _run(root).items
    salary_context_findings = [
        item
        for item in findings
        if item.rule == "pesose_icorps_salary_cost_context"
    ]

    assert len(salary_context_findings) == 2
    assert all(item.level == "error" for item in salary_context_findings)
    assert any(
        item.rule == "pesose_icorps_salary_support_missing"
        and item.level == "warning"
        for item in findings
    )


def test_pesose_icorps_unknown_cost_and_extra_member_are_manual_review(
    make_grant,
):
    budget = _compliant_pesose_icorps_budget()
    budget["other_direct_costs"] = [
        {
            "id": "unlisted-cost",
            "category": "Training support",
            "funds_per_year": 100,
            "icorps_amount": 200,
            "icorps_cost_type": "other_training_support",
        }
    ]
    budget["icorps_team"].append(
        {
            "name": "Co Lead",
            "role": "co_technical_lead",
            "agreed_to_program_requirements": True,
        }
    )
    config = _pesose_config(
        pesose={
            "icorps_waiver_dates": None,
            "icorps_budget_amount": 10_200,
            "public_product_citation_key": "product",
        }
    )
    root = _pesose_root_with_budget(make_grant, budget, config=config)
    hits = {
        item.rule: item.level
        for item in _run(root).items
        if item.rule.startswith("pesose_icorps_")
    }
    assert hits["pesose_icorps_cost_manual_review"] == "warning"
    assert hits["pesose_icorps_team_size_manual_review"] == "warning"
    assert "pesose_icorps_cost_not_allowed" not in hits


# -- CheckResult semantics ----------------------------------------------


def test_result_failed_semantics():
    err = CheckResult([CheckItem("error", "r", "m")])
    warn = CheckResult([CheckItem("warning", "r", "m")])
    clean = CheckResult([])
    assert err.failed() is True
    assert warn.failed() is False
    assert warn.failed(strict=True) is True
    assert clean.failed() is False
    assert clean.failed(strict=True) is False


def test_check_item_to_dict_shape():
    item = CheckItem("error", "rule_x", "msg", section="s", citation="c")
    d = item.to_dict()
    assert set(d) == {"level", "rule", "message", "section", "citation"}
    assert d["level"] == "error"


def test_placeholders_catch_bracketed_directives(tmp_path):
    from grantkit.core.project import find_placeholders

    text = (
        "Phone: [MAX: phone number]\n"
        "Budget: [NEED INPUT]\n"
        "Bios: [AK: confirm wording]\n"
        "Not placeholders: [2026 figures](https://example.com) and [@cite2026]."
    )
    found = find_placeholders(text)
    assert "[MAX: phone number]" in found
    assert "[NEED INPUT]" in found
    assert "[AK: confirm wording]" in found
    assert not any("example.com" in f or "@cite" in f for f in found)


def _plain_text_project(tmp_path, sections_yaml, files):
    import yaml as _yaml

    from grantkit.core.project import GrantProject

    (tmp_path / "responses").mkdir(exist_ok=True)
    for rel, body in files.items():
        (tmp_path / rel).write_text(body)
    (tmp_path / "grant.yaml").write_text(
        _yaml.safe_dump(
            {
                "title": "T",
                "accepts_markdown": False,
                "sections": sections_yaml,
            }
        )
    )
    return GrantProject(tmp_path)


def test_fields_sections_skip_plain_text_linting(tmp_path):
    from grantkit.core.checks import run_checks

    project = _plain_text_project(
        tmp_path,
        [
            {
                "id": "pi",
                "title": "PI details",
                "format": "fields",
                "file": "responses/pi.md",
            },
            {"id": "a", "title": "Summary", "file": "responses/a.md"},
        ],
        {
            "responses/pi.md": "| Field | Value |\n|---|---|\n| Name | Max |\n",
            "responses/a.md": "Plain prose only.\n",
        },
    )
    items = run_checks(project).items
    md = [i for i in items if i.rule == "markdown_in_plain_text"]
    assert md == []


def test_plain_text_severity_splits_by_convertibility(tmp_path):
    from grantkit.core.checks import run_checks

    project = _plain_text_project(
        tmp_path,
        [{"id": "a", "title": "Summary", "file": "responses/a.md"}],
        {
            "responses/a.md": (
                "Some **bold** claim.\n\n" "| a | b |\n|---|---|\n| 1 | 2 |\n"
            )
        },
    )
    items = [
        i
        for i in run_checks(project).items
        if i.rule == "markdown_in_plain_text"
    ]
    levels = {}
    for item in items:
        key = "table" if "convert" in item.message else "inline"
        levels.setdefault(key, set()).add(item.level)
    # Bold converts cleanly -> warning; tables survive -> error.
    assert any(i.level == "warning" for i in items)
    assert any(i.level == "error" for i in items)
    for item in items:
        if item.level == "error":
            assert "does not convert" in item.message
        else:
            assert "paste from the build output" in item.message

"""Scaffold a new grant project (``grantkit init``).

Produces the unified 0.2.0 layout that the rest of the engine reads:

* ``grant.yaml`` — funder / program / deadline plus the section table
  (``id``/``title``/``word_limit``/``char_limit``/``page_limit``/``required``/
  ``file``/``format``/``stage``).
* ``responses/<id>.md`` — one stub per section.
* ``budget.yaml`` — an empty, arithmetically-consistent budget skeleton.
* ``references.bib`` — an empty BibTeX file.

When ``--funder PACK_ID`` is given, sections and portal/locale defaults come
from the funder rule pack; otherwise a small generic skeleton is written.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

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
            _section_stub(
                section,
                accepts_markdown=accepts_markdown,
                pack_id=pack.id if pack else None,
            ),
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

    if pack and pack.id == "nsf-pesose-26-506-track-2":
        for relative_path, content in _pesose_support_files().items():
            support_path = root / relative_path
            support_path.parent.mkdir(parents=True, exist_ok=True)
            if support_path.exists() and not force:
                continue
            support_path.write_text(content, encoding="utf-8")
            created.append(support_path)

    return created


def _sections_for(pack: Optional[FunderPack]) -> list[dict]:
    if pack and pack.sections:
        out = []
        for section in pack.sections:
            file_rel = section.file or f"responses/{section.id}.md"
            item = {
                "id": section.id,
                "title": section.title,
                "word_limit": section.word_limit,
                "char_limit": section.char_limit,
                "page_limit": section.page_limit,
                "required": section.required,
                "file": file_rel,
                "format": section.format,
            }
            if section.stage is not None:
                item["stage"] = section.stage
            out.append(item)
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
        if pack.id == "nsf-pesose-26-506-track-2":
            config["pesose"] = _pesose_config_stub()
    config["accepts_markdown"] = pack.accepts_markdown if pack else True
    config["locale"] = pack.locale if pack else "en-US"
    config["references"] = "references.bib"
    config["budget"] = "budget.yaml"
    config["sections"] = sections
    return config


def _pesose_config_stub() -> dict:
    """Expose PESOSE evidence keys and copyable entry shapes."""
    from ..funders.nsf.pesose_compliance import (
        ALL_PROPOSAL_ATTESTATIONS,
        PRIOR_SUPPORT_REVIEW_ATTESTATIONS,
        TRACK_2_ACTIVITY_ATTESTATIONS,
    )

    return {
        "icorps_waiver_dates": None,
        "icorps_track1_award": None,
        "icorps_waiver_successfully_completed": False,
        "icorps_outcomes_described": False,
        "icorps_budget_amount": None,
        "public_product_citation_key": None,
        "public_product_open_source": False,
        "public_product_license": None,
        "compliance": {
            "proposal_submission_date": None,
            "pappg_conditional_requirements_reviewed": False,
            "eligibility": {
                "organization_type": None,
                "uei_is_valid_and_active": None,
                "sam_registration_is_valid_and_active": None,
                "single_lead_organization": None,
                "has_other_nsf_funded_organizations": None,
                "all_other_nsf_funded_organizations_are_subawardees": None,
                "all_subawardees_eligible": None,
                "has_non_nsf_supported_team_organizations": None,
                "all_non_nsf_supported_team_organizations_receive_no_nsf_support": None,
                "us_based_owned_and_controlled": None,
                "nonprofit_directly_associated_with_education_or_research": None,
                "for_profit_has_strong_scientific_or_engineering_capabilities": None,
                "ihe_is_accredited": None,
                "ihe_has_us_campus": None,
                "all_non_exception_senior_key_have_eligible_ihe_appointments": None,
                "no_pi_copi_or_senior_key_has_primary_appointment_at_overseas_us_ihe_branch": None,
                "has_senior_key_using_family_or_medical_leave_exception": None,
                "proposing_ihe_determined_leave_exception_senior_key_eligible": None,
                "has_foreign_academic_senior_key_or_collaborators": None,
                "all_foreign_academic_experts_are_essential_and_receive_no_nsf_support": None,
                "requests_funding_for_international_branch_campus": None,
                "international_branch_benefit_and_us_campus_infeasibility_justified": None,
                "international_branch_cover_sheet_box_checked": None,
                "international_branch_countries": None,
                "pi_is_employee_of_proposing_organization": None,
                "pi_normally_resident_in_us": None,
                "tribal_nation_is_federally_recognized": None,
                "federal_ffrdc_pappg_ie2_review_completed": None,
                "federal_ffrdc_pappg_ie2_exception_routes": None,
                "cognizant_nsf_program_officer_determined_federal_ffrdc_eligible_in_advance": None,
                "pi_has_legal_right_to_work": None,
                "has_other_pesose_funded_proposer_employees": None,
                "all_other_pesose_funded_proposer_employees_have_legal_right_to_work": None,
            },
            "letters": {
                "manifest": {},
                "manifest_entry_template": {
                    "mapping_key": "letters/example-user.pdf",
                    "writer_name": None,
                    "affiliation": None,
                    "project_relationship": None,
                    "page_count": None,
                    "independent_current_third_party_user_or_contributor": None,
                    "past_contribution": None,
                    "continuing_contribution": None,
                },
                "facilities_continuation": {
                    "depends_on_facilities_after_award": None,
                    "continuation_letter_file": None,
                    "writer_name": None,
                    "affiliation": None,
                    "project_relationship": None,
                    "page_count": None,
                    "extent_and_term_described": None,
                },
            },
            "personnel": {
                "declared_roster": [],
                "roster_entry_template": {
                    "full_name": None,
                    "organizations": None,
                    "role": None,
                },
                "roster_includes_all_required_personnel_classes": False,
            },
            "senior_key": {
                "declared_people": [],
                "documents": {},
                "document_entry_template": {
                    "mapping_key": "Senior/Key person's full name",
                    "biographical_sketch_file": None,
                    "current_and_pending_support_file": None,
                    "collaborators_and_other_affiliations_file": None,
                    "synergistic_activities_file": None,
                    "all_proposals_and_active_projects_disclosed": None,
                    "biographical_sketch_sciencv_certified": None,
                    "current_and_pending_support_sciencv_certified": None,
                    "current_and_pending_support_current_accurate_complete": None,
                    "coa_uses_unaltered_nsf_template": None,
                    "not_a_party_to_mftrp": None,
                    "synergistic_activities_page_count": None,
                    "synergistic_activities_example_count": None,
                    "research_security_training_completion_date": None,
                    "research_security_training_within_12_months_before_submission": None,
                },
            },
            "prior_nsf_support": {
                "has_pi_or_copi_with_current_or_recent_nsf_support": None,
                "results_from_prior_nsf_support_included": None,
                "all_covered_pi_copi_awards_included": None,
                "results_from_prior_nsf_support_within_five_pages": None,
                **{key: None for key in PRIOR_SUPPORT_REVIEW_ATTESTATIONS},
                "is_renewal_proposal": None,
            },
            "mentoring_plan": {
                "funds_postdoctoral_scholars_or_graduate_students": None,
                "unified_mentoring_plan_present": None,
                "mentoring_plan_page_count": None,
                "upload_file": None,
            },
            "supplement_1": {
                "proposing_organization_is_ihe": None,
                "foreign_affiliation_and_support_disclosure_documentation_maintained": None,
                "aor_certifies_all_senior_key_research_security_training_completed": None,
                "aor_certifies_all_senior_key_mftrp_certifications_complete": None,
                "aor_certifies_ihe_recr_training_plan": None,
                "ihe_maintains_confucius_institute_contract_or_agreement": None,
                "nsf_director_confucius_institute_waiver_approved": None,
                "dod_section_1062_waiver_requirements_fulfilled": None,
                "project_includes_nsf_funded_unmanned_aircraft_procurement_or_operation": None,
                "no_nsf_funds_for_covered_foreign_unmanned_aircraft_systems": None,
            },
            "dmsp": {
                "no_data_or_research_products": None,
                "no_product_justification_provided": None,
                "publication_supporting_data_expected": None,
                "publication_supporting_data_available_at_publication": None,
                "publication_sharing_exception_described_and_justified": None,
            },
            "manual_review": {
                key: False
                for key in (
                    *ALL_PROPOSAL_ATTESTATIONS,
                    *TRACK_2_ACTIVITY_ATTESTATIONS,
                )
            },
            "award_conditions": {
                "no_prohibited_person_or_entity_will_receive_or_participate": False,
            },
        },
    }


def _section_stub(
    section: dict,
    *,
    accepts_markdown: bool = True,
    pack_id: Optional[str] = None,
) -> str:
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
    if pack_id == "nsf-pesose-26-506-track-2":
        specialized = _pesose_section_body(section["id"])
        if specialized is not None:
            lines.extend(specialized)
            lines.append("")
            return "\n".join(lines)
    if accepts_markdown:
        lines.append(f"# {section['title']}")
        lines.append("")
    lines.append(PLACEHOLDER)
    lines.append("")
    return "\n".join(lines)


def _pesose_section_body(section_id: str) -> Optional[list[str]]:
    """Return source-shaped authoring prompts for PESOSE-only sections."""
    if section_id == "project_summary":
        return [
            "# Overview",
            "",
            PLACEHOLDER,
            "",
            "# Intellectual Merit",
            "",
            PLACEHOLDER,
            "",
            "# Broader Impacts",
            "",
            PLACEHOLDER,
            "",
            "Keywords: [TO BE COMPLETED]; [TO BE COMPLETED]",
        ]
    if section_id == "data_management_and_sharing_plan":
        from ..funders.nsf.pesose_compliance import DMSP_FIELDS

        lines = ["# Data Management and Sharing Plan", "", "## Product 1"]
        for field in DMSP_FIELDS:
            lines.extend([f"- **{field}:** {PLACEHOLDER}"])
        return lines
    if section_id == "personnel_collaborators":
        return [
            "# List of Project Personnel, Collaborators, and Partner Organizations",
            "",
            "| Full name | Organization(s) | Role in the project |",
            "|---|---|---|",
            f"| {PLACEHOLDER} | {PLACEHOLDER} | {PLACEHOLDER} |",
        ]
    return None


def _budget_stub(pack: Optional[FunderPack]) -> str:
    rate = 0.0
    note = ""
    if pack and pack.budget_rules and pack.budget_rules.currency:
        note = f"# Currency: {pack.budget_rules.currency}\n"
    skeleton: dict[str, Any] = {
        "years_in_budget": 1,
        "personnel": {"senior_key": [], "other": []},
        "fringe_benefits": {"rate": rate},
        "equipment": [],
        "travel": {"domestic": [], "foreign": []},
        "participant_support": [],
        "other_direct_costs": [],
        "indirect_costs": {"rate": rate},
    }
    if pack and pack.id == "nsf-pesose-26-506-track-2":
        skeleton["organization_type"] = None
        skeleton["years_in_budget"] = 2
        skeleton["fringe_benefits"].update(
            {
                "base": None,
                "breakdown": {},
                "salary_escalation_rates": {"year_1": 0, "year_2": 0},
                "budget_justification_includes_fringe_details": False,
            }
        )
        skeleton["indirect_costs"].update(
            {
                "method": "none",
                "has_current_nicra": None,
                "base": None,
                "base_amount": {"year_1": 0, "year_2": 0},
            }
        )
        skeleton["budget_justification_attestations"] = {
            "travel_breakdown_covers_each_trip": False,
            "materials_and_supplies_need_explained": False,
        }
        skeleton["icorps_team"] = []
        skeleton["icorps_salary_support_is_sufficient"] = False
        skeleton["icorps_budget_justification_includes_tagged_costs"] = False
        skeleton["icorps_training_format_acknowledged"] = "virtual"
        skeleton["evidence_templates"] = {
            "personnel_entry": {
                "name": None,
                "title": None,
                "responsibilities": None,
                "requested_salary_rate": None,
                "year_1": 0,
                "year_2": 0,
                "calendar_months": {"year_1": 0, "year_2": 0},
                "total_requested_salary": 0,
                "salary_calculation_basis": None,
                "calendar_months_reflect_requested_person_months": False,
                "budget_justification_includes_personnel_details": False,
                "employee_of_proposing_organization": None,
                "cumulative_nsf_person_months": {
                    "year_1": 0,
                    "year_2": 0,
                },
            },
            "personnel_bls_route": {
                "soc_code": None,
                "bls_url": None,
                "bls_percentile_rate": None,
                "bls_benchmark_is_non_c_level": False,
                "soc_responsibilities_match": False,
                "work_location": None,
                "bls_geographic_area": None,
                "bls_geography_matches_work_location": False,
                "above_bls_percentile_justification": None,
            },
            "personnel_existing_institutional_route": {
                "employment_status": "existing",
                "requested_rate_no_greater_than_current_attestation": False,
                "anticipated_institutional_escalation_rates": None,
            },
            "personnel_new_institutional_route": {
                "employment_status": "new",
                "salary_rate_consistent_with_written_policy": False,
                "escalation_rates_consistent_with_written_policy": False,
            },
            "equipment_entry": {
                "description": None,
                "necessity": None,
                "budget_justification_includes_description_and_necessity": False,
                "year_1": 0,
                "year_2": 0,
            },
            "travel_entry": {
                "description": None,
                "necessity": None,
                "breakdown": {},
                "cost_rule": None,
                "budget_justification_includes_description_necessity_and_breakdown": False,
                "year_1": 0,
                "year_2": 0,
            },
            "consultant_entry": {
                "category": "consultant",
                "description": None,
                "time_commitment": None,
                "consultant_rate": None,
                "responsibilities": None,
                "total_requested": None,
                "budget_justification_includes_consultant_details": False,
                "payee_is_owner_or_equity_holder": None,
                "signed_statement": {
                    "file": None,
                    "signed": False,
                    "confirms_availability": False,
                    "confirms_time_commitment": False,
                    "confirms_role": False,
                    "confirms_rate": False,
                },
                "year_1": 0,
                "year_2": 0,
            },
            "subaward_entry": {
                "category": "subaward",
                "institution": None,
                "purpose": None,
                "key_tasks": None,
                "requested_funding_amount": None,
                "budget_justification_includes_subaward_details": False,
                "payee_is_owner_or_equity_holder": None,
                "subaward_pi_statement": {
                    "included_in_budget_justification": False,
                    "signed_by_business_office": False,
                    "confirms_willingness": False,
                    "describes_responsibilities": False,
                    "file": None,
                },
                "subaward_budget_justification": {"file": None},
                "ip_rights_agreement": {"file": None},
                "co_pi_listed_on_line_a": False,
                "equipment": [],
                "travel": [],
                "year_1": 0,
                "year_2": 0,
            },
            "line_g_service_entry": {
                "category": "contractor",
                "description": None,
                "services_description": None,
                "budget_justification_includes_services_description": False,
                "payee_is_owner_or_equity_holder": None,
                "year_1": 0,
                "year_2": 0,
            },
        }
    header = (
        "# GrantKit budget. Line items feed `grantkit check` (arithmetic +\n"
        "# funder caps). See docs/artifacts.md for the schema.\n"
    )
    body: str = yaml.safe_dump(skeleton, sort_keys=False)
    return header + note + body


def _pesose_support_files() -> dict[str, str]:
    """Explain hard-coded PESOSE evidence directories in the scaffold."""
    return {
        "letters/README.md": (
            "# PESOSE letters\n\n"
            "Place the three to five independent current third-party user or "
            "contributor letter PDFs directly in this directory (not in "
            "nested folders), then key `pesose.compliance.letters.manifest` "
            "by each project-relative path, such as "
            "`letters/example-user.pdf`. If a separate facilities-"
            "continuation letter is required, place it here too and declare "
            "it under `letters.facilities_continuation`.\n"
        ),
        "senior-key/README.md": (
            "# Senior/Key documents\n\n"
            "Place each declared Senior/Key person's SciENcv biographical "
            "sketch PDF, SciENcv current-and-pending-support PDF, unaltered "
            "NSF COA `.xlsx`, and one-page synergistic-activities PDF here; "
            "map the project-relative paths under "
            "`pesose.compliance.senior_key.documents`.\n"
        ),
    }

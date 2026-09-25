"""Tests for `grantkit init` scaffolding."""

import pytest
import yaml

from grantkit.core.checks import run_checks
from grantkit.core.project import GrantProject
from grantkit.core.scaffold import ScaffoldError, init_project


def test_init_from_funder_pack(tmp_path):
    created = init_project(tmp_path, funder="nuffield-rda")
    names = {p.name for p in created}
    assert "grant.yaml" in names
    assert "budget.yaml" in names
    assert "references.bib" in names
    assert (tmp_path / "responses").is_dir()

    config = yaml.safe_load((tmp_path / "grant.yaml").read_text())
    assert config["pack"] == "nuffield-rda"
    assert config["accepts_markdown"] is False
    assert config["locale"] == "en-GB"
    assert len(config["sections"]) == 14
    for section in config["sections"]:
        assert {"id", "title", "required", "file"} <= set(section)


def test_fresh_plaintext_scaffold_has_no_errors(tmp_path):
    """A freshly scaffolded plain-text grant must not fail its own check."""
    init_project(tmp_path, funder="nuffield-rda")
    result = run_checks(GrantProject(tmp_path))
    # Only placeholder warnings from the stubs; no errors.
    assert result.errors == 0
    assert all(i.rule == "placeholder_text" for i in result.items)


def test_init_generic_without_funder(tmp_path):
    init_project(tmp_path)
    config = yaml.safe_load((tmp_path / "grant.yaml").read_text())
    assert config["accepts_markdown"] is True
    assert len(config["sections"]) == 2
    assert (tmp_path / "responses" / "summary.md").exists()


def test_init_refuses_existing_without_force(tmp_path):
    init_project(tmp_path)
    with pytest.raises(ScaffoldError):
        init_project(tmp_path)
    # Force overwrites cleanly.
    init_project(tmp_path, force=True)


def test_init_unknown_funder_raises(tmp_path):
    with pytest.raises(ScaffoldError):
        init_project(tmp_path, funder="not-a-real-pack")


def test_scaffolded_nsf_uses_markdown_headings(tmp_path):
    init_project(tmp_path, funder="nsf-pappg")
    body = (tmp_path / "responses" / "project_summary.md").read_text()
    assert "# Project Summary" in body  # markdown portal keeps headings


def test_scaffolded_pesose_uses_track_2_pack_and_current_sections(tmp_path):
    init_project(tmp_path, funder="nsf-pesose-26-506-track-2")
    config = yaml.safe_load((tmp_path / "grant.yaml").read_text())
    assert config["pack"] == "nsf-pesose-26-506-track-2"
    sections = {section["id"]: section for section in config["sections"]}
    assert sections["project_summary"]["page_limit"] == 1
    assert sections["project_description"]["page_limit"] == 15
    assert sections["data_management_and_sharing_plan"]["format"] == "fields"
    assert (
        sections["data_management_and_sharing_plan"]["stage"]
        == "research_gov_webform"
    )
    assert "broader_impacts" not in sections
    compliance = config["pesose"]["compliance"]
    assert {
        "proposal_submission_date",
        "eligibility",
        "letters",
        "personnel",
        "senior_key",
        "prior_nsf_support",
        "mentoring_plan",
        "supplement_1",
        "dmsp",
        "manual_review",
    } <= set(compliance)
    eligibility = compliance["eligibility"]
    assert {
        "organization_type",
        "uei_is_valid_and_active",
        "sam_registration_is_valid_and_active",
        "single_lead_organization",
        "pi_has_legal_right_to_work",
        "no_pi_copi_or_senior_key_has_primary_appointment_at_overseas_us_ihe_branch",
    } <= set(eligibility)
    letters = compliance["letters"]
    assert letters["manifest"] == {}
    assert {
        "mapping_key",
        "writer_name",
        "affiliation",
        "project_relationship",
        "page_count",
        "independent_current_third_party_user_or_contributor",
        "past_contribution",
        "continuing_contribution",
    } <= set(letters["manifest_entry_template"])
    assert {
        "depends_on_facilities_after_award",
        "continuation_letter_file",
        "extent_and_term_described",
    } <= set(letters["facilities_continuation"])
    assert {
        "biographical_sketch_file",
        "current_and_pending_support_file",
        "collaborators_and_other_affiliations_file",
        "synergistic_activities_file",
    } <= set(compliance["senior_key"]["document_entry_template"])
    assert (
        compliance["letters"]["manifest_entry_template"]["mapping_key"]
        == "letters/example-user.pdf"
    )
    assert "mapping_key" in compliance["senior_key"]["document_entry_template"]
    assert compliance["manual_review"]
    assert compliance["award_conditions"] == {
        "no_prohibited_person_or_entity_will_receive_or_participate": False
    }

    dmsp_body = (
        tmp_path / "responses" / "data_management_and_sharing_plan.md"
    ).read_text()
    assert "## Product 1" in dmsp_body
    for field in (
        "Data or research product category",
        "Access policies and limitations",
        "Data standards and metadata",
        "Data or research product provenance",
        "Public archiving",
        "Timeline for public accessibility",
        "Data availability",
        "Accountability",
    ):
        assert f"**{field}:**" in dmsp_body

    personnel_body = (
        tmp_path / "responses" / "personnel_collaborators.md"
    ).read_text()
    assert (
        "| Full name | Organization(s) | Role in the project |"
        in personnel_body
    )
    assert (tmp_path / "letters" / "README.md").exists()
    assert (
        "directly in this directory"
        in (tmp_path / "letters" / "README.md").read_text()
    )
    assert (tmp_path / "senior-key" / "README.md").exists()

    budget = yaml.safe_load((tmp_path / "budget.yaml").read_text())
    assert budget["organization_type"] is None
    assert {
        "personnel_entry",
        "personnel_bls_route",
        "personnel_existing_institutional_route",
        "personnel_new_institutional_route",
        "equipment_entry",
        "travel_entry",
        "consultant_entry",
        "subaward_entry",
        "line_g_service_entry",
    } <= set(budget["evidence_templates"])
    travel = budget["evidence_templates"]["travel_entry"]
    assert {
        "description",
        "necessity",
        "breakdown",
        "cost_rule",
        "budget_justification_includes_description_necessity_and_breakdown",
    } <= set(travel)
    for key in ("consultant_entry", "subaward_entry", "line_g_service_entry"):
        assert "category" in budget["evidence_templates"][key]
    assert {
        "included_in_budget_justification",
        "signed_by_business_office",
        "confirms_willingness",
        "describes_responsibilities",
        "file",
    } <= set(
        budget["evidence_templates"]["subaward_entry"]["subaward_pi_statement"]
    )

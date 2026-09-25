"""Tests for funder rule packs and the pack schema."""

import pytest

from grantkit.packs import (
    list_pack_ids,
    load_pack,
    load_pack_dict,
    resolve_pack,
    validate_pack,
)
from grantkit.packs.schema import FunderPack

EXPECTED_PACKS = {
    "nsf-pappg",
    "nsf-pesose-26-506-track-2",
    "nuffield-rda",
    "pbif",
}


def test_all_packs_present():
    assert EXPECTED_PACKS.issubset(set(list_pack_ids()))


@pytest.mark.parametrize("pack_id", sorted(EXPECTED_PACKS))
def test_packs_are_schema_valid(pack_id):
    errors = validate_pack(load_pack_dict(pack_id))
    assert errors == [], f"{pack_id}: {errors}"


@pytest.mark.parametrize("pack_id", sorted(EXPECTED_PACKS))
def test_packs_load(pack_id):
    pack = load_pack(pack_id)
    assert isinstance(pack, FunderPack)
    assert pack.id == pack_id
    assert pack.name


def test_pack_id_matches_filename_stem():
    for pack_id in EXPECTED_PACKS:
        assert load_pack(pack_id).id == pack_id


# -- schema validation --------------------------------------------------


def test_schema_requires_id_and_name():
    errors = validate_pack({})
    assert any("id" in e for e in errors)
    assert any("name" in e for e in errors)


def test_schema_rejects_bad_locale():
    errors = validate_pack({"id": "x", "name": "X", "locale": "fr-FR"})
    assert any("locale" in e for e in errors)


def test_schema_rejects_bad_content_engine():
    errors = validate_pack(
        {"id": "x", "name": "X", "content_engine": "does_not_exist"}
    )
    assert any("content_engine" in e for e in errors)


def test_schema_rejects_duplicate_section_ids():
    errors = validate_pack(
        {
            "id": "x",
            "name": "X",
            "sections": [
                {"id": "a", "title": "A"},
                {"id": "a", "title": "A2"},
            ],
        }
    )
    assert any("duplicate" in e for e in errors)


def test_schema_rejects_non_integer_word_limit():
    errors = validate_pack(
        {
            "id": "x",
            "name": "X",
            "sections": [{"id": "a", "title": "A", "word_limit": "lots"}],
        }
    )
    assert any("word_limit" in e for e in errors)


def test_schema_rejects_bad_severity():
    errors = validate_pack(
        {
            "id": "x",
            "name": "X",
            "formatting_rules": [
                {"id": "r", "description": "d", "severity": "fatal"}
            ],
        }
    )
    assert any("severity" in e for e in errors)


@pytest.mark.parametrize(
    "extra",
    [
        {"locale": {}},
        {"content_engine": []},
        {"program": []},
        {"sections": [{"id": [], "title": "A", "format": []}]},
        {
            "formatting_rules": [
                {"id": "r", "description": "Rule", "severity": []}
            ]
        },
        {"budget_rules": {"mtdc_excludes": [1], "currency": []}},
        {"portal": {"url": []}},
        {"review_rubric": [{"id": [], "name": "Criterion"}]},
    ],
    ids=(
        "locale",
        "content-engine",
        "top-text",
        "section",
        "formatting-rule",
        "budget-rule",
        "portal",
        "rubric",
    ),
)
def test_schema_rejects_wrong_shaped_known_fields(extra):
    data = {"id": "x", "name": "X", **extra}
    assert validate_pack(data)


@pytest.mark.parametrize(
    "extra, needle",
    [
        ({"extends": ""}, "extends"),
        ({"proposal_rules": {"title_prefix": ""}}, "title_prefix"),
        (
            {
                "attachment_groups": [
                    {"id": "letters", "title": "Letters", "glob": "../*.pdf"}
                ]
            },
            "within the grant project",
        ),
        (
            {
                "attachment_groups": [
                    {
                        "id": "letters",
                        "title": "Letters",
                        "glob": "letters/*.pdf",
                        "page_limit_each": 0,
                    }
                ]
            },
            "positive integer",
        ),
        (
            {"budget_rules": {"preparation": {"bls_salary_percentile": 101}}},
            "bls_salary_percentile",
        ),
        (
            {
                "budget_rules": {
                    "preparation": {
                        "materials_explanation_threshold_fraction": 0
                    }
                }
            },
            "materials_explanation_threshold_fraction",
        ),
        (
            {
                "budget_rules": {
                    "preparation": {
                        "equity_owner_payment_channels": ["employee"]
                    }
                }
            },
            "unknown channel",
        ),
        (
            {"budget_rules": {"preparation": {"max_budget_years": 0}}},
            "max_budget_years",
        ),
        (
            {
                "budget_rules": {
                    "preparation": {
                        "indirect_base_amount_verification_required": "yes"
                    }
                }
            },
            "indirect_base_amount_verification_required",
        ),
    ],
)
def test_schema_rejects_invalid_inheritance_and_attachment_rules(
    extra, needle
):
    errors = validate_pack({"id": "x", "name": "X", **extra})
    assert any(needle in error for error in errors)


@pytest.mark.parametrize("value", ["\ud800", "\x1b[31m", "\x00"])
def test_schema_rejects_unsafe_pack_text(value):
    assert validate_pack({"id": "x", "name": value})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    "key", ["total_cap", "annual_cap", "indirect_rate_max"]
)
def test_schema_rejects_non_finite_budget_rules(key, value):
    errors = validate_pack(
        {"id": "x", "name": "X", "budget_rules": {key: value}}
    )
    assert any(f"budget_rules.{key}" in error for error in errors)


# -- NSF pack: preserves the folded-in PAPPG rules + citations ----------


def test_nsf_pack_preserves_rules_and_citations():
    pack = load_pack("nsf-pappg")
    assert pack.content_engine == "nsf_pappg"
    assert pack.locale == "en-US"
    # The stable base pack retains its folded legacy rule inventory. Programs
    # that need current metadata can replace this list through inheritance.
    assert len(pack.formatting_rules) >= 25
    # Every rule carries a citation.
    for rule in pack.formatting_rules:
        assert rule.citation, f"rule {rule.id} missing citation"
    ids = {r.id for r in pack.formatting_rules}
    for expected in (
        "font_size_minimum",
        "margins_minimum",
        "no_hyperlinks_in_project_description",
        "no_cloud_storage_urls",
        "required_intellectual_merit",
        "required_broader_impacts",
    ):
        assert expected in ids
    assert any(r.url and "nsf24001" in r.url for r in pack.formatting_rules)
    # NSF merit-review rubric is available for `grantkit review`.
    rubric_ids = {c.id for c in pack.review_rubric}
    assert {"intellectual_merit", "broader_impacts"} <= rubric_ids


def test_pesose_track_2_pack_inherits_nsf_and_encodes_solicitation():
    pack = load_pack("nsf-pesose-26-506-track-2")
    assert pack.extends == "nsf-pappg"
    assert pack.content_engine == "nsf_pesose_26_506_track_2"
    assert pack.proposal_rules is not None
    assert pack.proposal_rules.title_prefix == "PESOSE: Track 2: "
    assert pack.proposal_rules.max_duration_months == 24
    assert pack.budget_rules is not None
    assert pack.budget_rules.total_cap == 1_500_000
    assert pack.budget_rules.indirect_rate_max is None
    preparation = pack.budget_rules.preparation
    assert preparation is not None
    assert preparation.max_budget_years == 2
    assert preparation.institutional_salary_org_types == [
        "higher_education",
        "state_government",
        "local_government",
    ]
    assert preparation.bls_salary_org_types == ["nonprofit", "for_profit"]
    assert preparation.bls_salary_percentile == 75
    assert preparation.lines_ab_employee_only is True
    assert preparation.salary_months_justification_threshold == 2
    assert preparation.materials_explanation_threshold_fraction == 0.10
    assert preparation.consultant_statement_threshold == 50_000
    assert preparation.subaward_ip_rights_agreement_required is True
    assert preparation.subaward_equipment_allowed is False
    assert preparation.de_minimis_indirect_rate == 0.15
    assert preparation.de_minimis_indirect_base == "mtdc"
    assert preparation.indirect_base_amount_verification_required is True
    assert preparation.salary_hourly_month_hours == 173.33
    assert preparation.main_equipment_necessity_required is True
    assert preparation.travel_cost_rules == {
        "for_profit": "48_cfr_31_205_46",
        "default": "2_cfr_200_475",
    }
    assert preparation.consultant_justification_fields == [
        "time_commitment",
        "consultant_rate",
        "responsibilities",
        "total_requested",
    ]
    assert preparation.line_g_services_description_required is True
    assert preparation.icorps_budget_cap == 30_000
    assert preparation.icorps_required_team_roles == [
        "technical_lead",
        "entrepreneurial_lead",
        "industry_mentor",
    ]
    assert preparation.icorps_team_size_manual_review_max == 3
    assert preparation.icorps_training_format == "virtual"
    assert preparation.url and preparation.url.endswith("/updates/120507")

    limits = {section.id: section.page_limit for section in pack.sections}
    assert limits["project_summary"] == 1
    assert limits["project_description"] == 15
    assert limits["budget_justification"] == 5
    dmsp = next(
        section
        for section in pack.sections
        if section.id == "data_management_and_sharing_plan"
    )
    assert dmsp.format == "fields"
    assert dmsp.stage == "research_gov_webform"

    # The conditional facilities-continuation letter is separate from the
    # 3-5 third-party letters, so the programmatic PESOSE validator owns the
    # nuanced inventory and page-count reconciliation.
    assert pack.attachment_groups == []

    effective_rule_ids = {rule.id for rule in pack.formatting_rules}
    assert {
        "font_approved_families_and_sizes",
        "margins_minimum",
        "project_summary_required_components",
        "project_description_required_broader_impacts",
        "no_urls_in_project_description",
    } <= effective_rule_ids
    assert "required_overview" not in effective_rule_ids
    font_rule = next(
        rule
        for rule in pack.formatting_rules
        if rule.id == "font_approved_families_and_sizes"
    )
    assert "Arial" in font_rule.description
    assert "Times New Roman" in font_rule.description
    assert "11 points" in font_rule.description
    assert font_rule.citation == "PAPPG 24-1 II.C.2.a"
    assert font_rule.url and font_rule.url.endswith("#2C2")
    for rule_id in (
        "font_exception_scope",
        "uploaded_sections_use_same_formatting",
    ):
        rule = next(
            rule for rule in pack.formatting_rules if rule.id == rule_id
        )
        assert rule.severity == "error"
    pagination_rule = next(
        rule
        for rule in pack.formatting_rules
        if rule.id == "omit_proposer_page_numbers"
    )
    assert pagination_rule.citation == "PAPPG 24-1 II.C.1"
    assert pagination_rule.url and pagination_rule.url.endswith("#2C1")
    rubric_ids = {criterion.id for criterion in pack.review_rubric}
    assert {"intellectual_merit", "broader_impacts"} <= rubric_ids
    assert {
        "societal_or_national_importance",
        "long_term_sustainability",
        "contributor_community_and_organization",
        "licensing_approach",
        "build_test_quality_and_security",
        "milestones_and_evaluation",
    } <= rubric_ids


def test_pack_inheritance_merges_mappings_and_replaces_lists(monkeypatch):
    from grantkit.packs import registry

    packs = {
        "base": {
            "id": "base",
            "name": "Base",
            "budget_rules": {"total_cap": None, "currency": "USD"},
            "sections": [{"id": "base", "title": "Base"}],
        },
        "child": {
            "id": "child",
            "name": "Child",
            "extends": "base",
            "budget_rules": {"total_cap": 10},
            "sections": [{"id": "child", "title": "Child"}],
        },
    }
    monkeypatch.setattr(registry, "load_pack_dict", packs.__getitem__)
    resolved = registry._resolve_pack_dict("child")
    assert resolved["budget_rules"] == {"total_cap": 10, "currency": "USD"}
    assert resolved["sections"] == [{"id": "child", "title": "Child"}]


def test_pack_inheritance_rejects_cycles_and_unknown_parents(monkeypatch):
    from grantkit.packs import registry

    packs = {
        "a": {"id": "a", "name": "A", "extends": "b"},
        "b": {"id": "b", "name": "B", "extends": "a"},
    }
    monkeypatch.setattr(registry, "load_pack_dict", packs.__getitem__)
    with pytest.raises(ValueError, match="inheritance cycle"):
        registry._resolve_pack_dict("a")

    packs["a"]["extends"] = "missing"
    with pytest.raises(KeyError, match="extends unknown pack"):
        registry._resolve_pack_dict("a")


# -- Nuffield pack: values sourced from the reference grant -------------


def test_nuffield_pack_matches_reference_values():
    pack = load_pack("nuffield-rda")
    assert pack.locale == "en-GB"
    assert pack.accepts_markdown is False  # plain-text portal
    limits = {s.id: s.word_limit for s in pack.sections}
    # Sourced verbatim from the full_application block of the reference grant.
    assert limits["project_summary"] == 250
    assert limits["b_case_for_importance"] == 700
    assert limits["d_methods_approach_activities"] == 2800
    assert pack.budget_rules is not None
    assert pack.budget_rules.total_cap == 500000
    assert pack.budget_rules.currency == "GBP"


# -- PBIF pack: no invented limits --------------------------------------


def test_pbif_pack_matches_round_2_requirements():
    pack = load_pack("pbif")
    # The six narrative sections from PBIF's Spring 2026 round-2 application
    # materials, in order.
    assert [s.id for s in pack.sections] == [
        "impact",
        "catalytic_rationale",
        "technical_feasibility",
        "practical_feasibility",
        "responsible_deployment",
        "scaling",
    ]
    assert all(s.required for s in pack.sections)
    # The 8-page limit applies to the combined narrative, so it lives in
    # formatting_rules, not per-section limits. No per-section word limits
    # are published — absence of a limit means unknown, not unlimited.
    for section in pack.sections:
        assert section.word_limit is None
        assert section.char_limit is None
        assert section.page_limit is None
    assert any(r.id == "narrative_page_limit" for r in pack.formatting_rules)
    # Pilot track: up to $2M, indirect capped at 10%.
    assert pack.budget_rules is not None
    assert pack.budget_rules.total_cap == 2000000
    assert pack.budget_rules.indirect_rate_max == 0.10
    # Official five-criterion reviewer rubric drives `grantkit review`.
    assert [c.id for c in pack.review_rubric] == [
        "impact",
        "responsible_deployment",
        "feasibility",
        "strategic_alignment",
        "shared_learning",
    ]


# -- resolution ---------------------------------------------------------


def test_resolve_pack_by_id_and_name():
    assert resolve_pack("nsf-pappg").id == "nsf-pappg"
    assert resolve_pack("National Science Foundation").id == "nsf-pappg"
    assert resolve_pack("Nuffield Foundation").id == "nuffield-rda"


def test_resolve_pack_unknown_returns_none():
    assert resolve_pack("not-a-real-funder-xyz") is None
    assert resolve_pack(None) is None


def test_pack_schema_rejects_invalid_section_format():
    from grantkit.packs.schema import validate_pack

    errors = validate_pack(
        {
            "id": "x",
            "name": "X",
            "sections": [{"id": "s", "title": "S", "format": "tabular"}],
        }
    )
    assert any("invalid format" in e for e in errors)
    assert not validate_pack(
        {
            "id": "x",
            "name": "X",
            "sections": [{"id": "s", "title": "S", "format": "fields"}],
        }
    )

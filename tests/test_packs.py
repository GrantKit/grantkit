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

EXPECTED_PACKS = {"nsf-pappg", "nuffield-rda", "pbif"}


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


# -- NSF pack: preserves the folded-in PAPPG rules + citations ----------


def test_nsf_pack_preserves_rules_and_citations():
    pack = load_pack("nsf-pappg")
    assert pack.content_engine == "nsf_pappg"
    assert pack.locale == "en-US"
    # A substantial rule set carried over from nsf_formatting_rules.yaml.
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
    # Citations point at the PAPPG URL.
    assert any(r.url and "nsf24001" in r.url for r in pack.formatting_rules)
    # NSF merit-review rubric is available for `grantkit review`.
    rubric_ids = {c.id for c in pack.review_rubric}
    assert {"intellectual_merit", "broader_impacts"} <= rubric_ids


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


def test_pbif_pack_has_no_invented_limits():
    pack = load_pack("pbif")
    assert len(pack.sections) == 15
    # No word/char/page limits were sourced, so none are encoded.
    for section in pack.sections:
        assert section.word_limit is None
        assert section.char_limit is None
    assert pack.budget_rules is not None
    assert pack.budget_rules.total_cap is None  # request != cap


# -- resolution ---------------------------------------------------------


def test_resolve_pack_by_id_and_name():
    assert resolve_pack("nsf-pappg").id == "nsf-pappg"
    assert resolve_pack("National Science Foundation").id == "nsf-pappg"
    assert resolve_pack("Nuffield Foundation").id == "nuffield-rda"


def test_resolve_pack_unknown_returns_none():
    assert resolve_pack("not-a-real-funder-xyz") is None
    assert resolve_pack(None) is None

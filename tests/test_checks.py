"""Tests for the check runner."""

from grantkit.core.checks import CheckItem, CheckResult, run_checks
from grantkit.core.project import GrantProject


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


def test_plain_text_portal_flags_markdown(make_grant, simple_config):
    config = dict(simple_config)
    config["accepts_markdown"] = False
    root = make_grant(
        config,
        {
            "responses/summary.md": "# A heading\n\nBody text.",
            "responses/narrative.md": "Plain text is fine here.",
        },
    )
    result = _run(root)
    md = [i for i in result.items if i.rule == "markdown_in_plain_text"]
    assert md and all(i.level == "error" for i in md)
    assert md[0].section == "summary"


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

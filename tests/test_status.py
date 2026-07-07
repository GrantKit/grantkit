"""Tests for the status.json contract."""

import json
from datetime import date, timedelta

from grantkit import __version__
from grantkit.core.project import GrantProject
from grantkit.core.status import (
    build_status,
    days_until_deadline,
    write_status,
)

TOP_LEVEL_KEYS = {
    "grantkit_version",
    "generated_at",
    "grant",
    "completion",
    "sections",
    "checks",
}
GRANT_KEYS = {"title", "funder", "program", "deadline"}
COMPLETION_KEYS = {
    "sections_total",
    "sections_complete",
    "words_total",
    "percent",
}
SECTION_KEYS = {"id", "title", "words", "word_limit", "status", "issues"}
CHECK_KEYS = {"errors", "warnings", "items"}
ITEM_KEYS = {"level", "rule", "message", "section", "citation"}
VALID_STATUSES = {"complete", "partial", "empty", "over_limit"}


def _status(make_grant, simple_config, responses):
    root = make_grant(simple_config, responses)
    return build_status(GrantProject(root)), root


def test_status_top_level_contract(make_grant, simple_config):
    status, _ = _status(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Summary content for the grant here.",
            "responses/narrative.md": "Narrative content, short but real.",
        },
    )
    assert set(status) == TOP_LEVEL_KEYS
    assert status["grantkit_version"] == __version__
    assert isinstance(status["generated_at"], str)
    assert set(status["grant"]) == GRANT_KEYS
    assert set(status["completion"]) == COMPLETION_KEYS
    assert set(status["checks"]) == CHECK_KEYS


def test_status_grant_block(make_grant, simple_config):
    status, _ = _status(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Summary content.",
            "responses/narrative.md": "Narrative content.",
        },
    )
    grant = status["grant"]
    assert grant["title"] == "Test Grant"
    assert grant["funder"] == "Test Foundation"
    assert grant["program"] == "Test Program"
    assert grant["deadline"] == "2099-12-31"


def test_status_sections_shape_and_statuses(make_grant, simple_config):
    status, _ = _status(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Real summary content is present.",
            "responses/narrative.md": "word " * 200,  # over the 50 limit
        },
    )
    for section in status["sections"]:
        assert set(section) == SECTION_KEYS
        assert section["status"] in VALID_STATUSES
        assert isinstance(section["issues"], list)
    by_id = {s["id"]: s for s in status["sections"]}
    assert by_id["narrative"]["status"] == "over_limit"
    assert by_id["summary"]["status"] == "complete"


def test_status_completion_math(make_grant, simple_config):
    status, _ = _status(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Complete summary content present.",
            # narrative missing -> empty
        },
    )
    completion = status["completion"]
    assert completion["sections_total"] == 2
    assert completion["sections_complete"] == 1
    assert completion["percent"] == 50.0
    assert isinstance(completion["words_total"], int)


def test_status_checks_items_shape(make_grant, simple_config):
    config = dict(simple_config)
    config["accepts_markdown"] = False
    status, _ = _status(
        make_grant,
        config,
        {
            "responses/summary.md": "| a | b |\n|---|---|\n| 1 | 2 |",
            "responses/narrative.md": "plain text ok",
        },
    )
    checks = status["checks"]
    assert checks["errors"] >= 1
    for item in checks["items"]:
        assert set(item) == ITEM_KEYS
        assert item["level"] in {"error", "warning"}


def test_write_status_roundtrips(make_grant, simple_config):
    root = make_grant(
        simple_config,
        {
            "responses/summary.md": "Summary content.",
            "responses/narrative.md": "Narrative content.",
        },
    )
    out = write_status(GrantProject(root))
    assert out == root / "status.json"
    loaded = json.loads(out.read_text())
    assert set(loaded) == TOP_LEVEL_KEYS


def test_days_until_deadline():
    future = (date.today() + timedelta(days=10)).isoformat()
    past = (date.today() - timedelta(days=3)).isoformat()
    assert days_until_deadline(future) == 10
    assert days_until_deadline(past) == -3
    assert days_until_deadline(None) is None
    assert days_until_deadline("not-a-date") is None

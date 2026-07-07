"""Tests for the review packet."""

from grantkit.core.project import GrantProject
from grantkit.core.review import build_review


def _project(make_grant, config, responses):
    return GrantProject(make_grant(config, responses))


def test_review_packet_shape(make_grant, simple_config):
    project = _project(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Summary body.",
            "responses/narrative.md": "Narrative body.",
        },
    )
    packet = build_review(project)
    assert set(packet) >= {
        "grantkit_version",
        "grant",
        "rubric",
        "sections",
        "checks",
    }
    assert "pack" not in packet
    # Section bodies are included for the agent to review.
    bodies = {s["id"]: s["body"] for s in packet["sections"]}
    assert bodies["summary"] == "Summary body."


def test_review_includes_rubric_from_pack(make_grant):
    config = {
        "title": "NSF grant",
        "pack": "nsf-pappg",
        "deadline": "2099-01-01",
        "accepts_markdown": True,
        "sections": [
            {
                "id": "project_summary",
                "title": "Project Summary",
                "required": True,
                "file": "responses/project_summary.md",
            }
        ],
    }
    project = _project(
        make_grant,
        config,
        {"responses/project_summary.md": "# Project Summary\n\nBody."},
    )
    packet = build_review(project)
    rubric_ids = {c["id"] for c in packet["rubric"]}
    assert "intellectual_merit" in rubric_ids


def test_review_pack_flag_embeds_full_pack(make_grant):
    config = {
        "title": "NSF grant",
        "pack": "nsf-pappg",
        "deadline": "2099-01-01",
        "accepts_markdown": True,
        "sections": [
            {
                "id": "project_summary",
                "title": "Project Summary",
                "required": True,
                "file": "responses/project_summary.md",
            }
        ],
    }
    project = _project(
        make_grant,
        config,
        {"responses/project_summary.md": "# Project Summary\n\nBody."},
    )
    packet = build_review(project, include_pack=True)
    assert "pack" in packet
    assert packet["pack"]["id"] == "nsf-pappg"
    assert "formatting_rules" in packet["pack"]

"""Tests for `grantkit build`."""

import json

import pytest

from grantkit.core.builder import build_project
from grantkit.core.project import GrantProject


def _project(make_grant, config, responses):
    return GrantProject(make_grant(config, responses))


def test_build_md_markdown_portal(make_grant, simple_config):
    project = _project(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "The summary body.",
            "responses/narrative.md": "The narrative body.",
        },
    )
    result = build_project(project, fmt="md")
    text = result.document_path.read_text()
    assert result.document_path.name == "proposal.md"
    assert "## Summary" in text
    assert "The narrative body." in text
    # status.json always written.
    assert result.status_path.exists()


def test_build_plain_text_portal_copy_blocks(make_grant, simple_config):
    config = dict(simple_config)
    config["accepts_markdown"] = False
    project = _project(
        make_grant,
        config,
        {
            "responses/summary.md": "Plain summary text.",
            "responses/narrative.md": "Plain narrative text.",
        },
    )
    result = build_project(project, fmt="md")
    text = result.document_path.read_text()
    assert "paste each block" in text
    assert "Summary" in text
    assert "words)" in text  # per-block word count label


def test_build_html_document(make_grant, simple_config):
    project = _project(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Summary body.",
            "responses/narrative.md": "Narrative body.",
        },
    )
    result = build_project(project, fmt="html")
    html = result.document_path.read_text()
    assert result.document_path.name == "proposal.html"
    assert "<html" in html
    assert "Summary body." in html


def test_build_share_page(make_grant, simple_config):
    project = _project(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Summary body content.",
            "responses/narrative.md": "word " * 200,  # over limit -> badge
        },
    )
    result = build_project(project, fmt="md", share=True)
    assert result.share_path.name == "assembled.html"
    page = result.share_path.read_text()
    assert 'class="badge"' in page
    assert "over limit" in page  # narrative badge
    assert "complete" in page  # summary badge
    assert result.status_path.exists()


def test_build_always_writes_status_json(make_grant, simple_config):
    project = _project(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Summary body.",
            "responses/narrative.md": "Narrative body.",
        },
    )
    result = build_project(project, fmt="md")
    status = json.loads(result.status_path.read_text())
    assert status["grantkit_version"] == "0.2.0"
    assert "checks" in status


def test_build_docx(make_grant, simple_config):
    pytest.importorskip("docx")
    project = _project(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Summary body.",
            "responses/narrative.md": "Narrative body.",
        },
    )
    result = build_project(project, fmt="docx")
    assert result.document_path.name == "proposal.docx"
    assert result.document_path.exists()
    assert result.document_path.stat().st_size > 0


def test_build_rejects_unknown_format(make_grant, simple_config):
    project = _project(
        make_grant,
        simple_config,
        {
            "responses/summary.md": "Body.",
            "responses/narrative.md": "Body.",
        },
    )
    with pytest.raises(ValueError):
        build_project(project, fmt="rtf")


def test_plaintext_blocks_render_fields_sections_verbatim(tmp_path):
    import yaml as _yaml

    from grantkit.core.builder import _assemble_plaintext_blocks
    from grantkit.core.project import GrantProject

    (tmp_path / "responses").mkdir()
    (tmp_path / "responses" / "pi.md").write_text(
        "| Field | Value |\n|---|---|\n| Name | Max |\n"
    )
    (tmp_path / "responses" / "a.md").write_text("Some **bold** prose.\n")
    (tmp_path / "grant.yaml").write_text(
        _yaml.safe_dump(
            {
                "title": "T",
                "accepts_markdown": False,
                "sections": [
                    {
                        "id": "pi",
                        "title": "PI details",
                        "format": "fields",
                        "file": "responses/pi.md",
                    },
                    {
                        "id": "a",
                        "title": "Summary",
                        "file": "responses/a.md",
                        "word_limit": 100,
                    },
                ],
            }
        )
    )
    blocks = _assemble_plaintext_blocks(GrantProject(tmp_path))
    assert "PI details  (form fields — enter individually)" in blocks
    assert "| Name | Max |" in blocks  # fields table kept verbatim
    assert "Some bold prose." in blocks  # emphasis stripped in prose
    assert "**bold**" not in blocks


def test_to_plaintext_strips_html_comments():
    from grantkit.core.builder import _to_plaintext

    assert _to_plaintext("Keep this.<!-- reviewer note\nspanning -->") == (
        "Keep this."
    )

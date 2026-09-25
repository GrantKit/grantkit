"""Focused coverage for the high-level NSF review-PDF build."""

import sys
from types import ModuleType

from click.testing import CliRunner

from grantkit.cli import main
from grantkit.core.builder import build_project
from grantkit.core.project import GrantProject


def _install_fake_weasyprint(monkeypatch):
    captured = {}
    module = ModuleType("weasyprint")

    class FakeHTML:
        def __init__(self, *, string):
            captured["html"] = string

        def write_pdf(self, path):
            with open(path, "wb") as pdf:
                pdf.write(b"%PDF synthetic")

    module.HTML = FakeHTML
    monkeypatch.setitem(sys.modules, "weasyprint", module)
    return captured


def _nsf_project(make_grant, simple_config):
    config = dict(simple_config)
    config["pack"] = "nsf-pappg"
    config["funder"] = "National Science Foundation"
    root = make_grant(
        config,
        {
            "responses/summary.md": "Evidence [@source].",
            "responses/narrative.md": "Narrative body.",
        },
    )
    return root, GrantProject(root)


def test_nsf_pdf_is_unmistakably_review_only_and_uses_safe_css(
    make_grant, simple_config, monkeypatch
):
    captured = _install_fake_weasyprint(monkeypatch)
    _, project = _nsf_project(make_grant, simple_config)

    result = build_project(project, fmt="pdf")

    html = captured["html"]
    assert "REVIEW COPY — NOT FOR NSF SUBMISSION" in html
    assert "Do not upload it to NSF" in html
    assert "separately in Research.gov" in html
    assert "does not resolve or format" in html
    assert "[@source]" in html

    assert "size: 8.5in 11in" in html
    assert "margin: 1.0in 1.0in 1.0in 1.0in" in html
    assert 'font-family: "Arial"' in html
    assert "font-size: 10pt" in html
    assert "line-height: 1.2" in html
    assert "counter(page)" not in html
    assert "Georgia" not in html
    assert "Segoe UI" not in html

    assert result.document_path.name == "proposal.pdf"
    assert result.document_path.exists()
    assert any("review copies only" in warning for warning in result.warnings)
    assert any(
        "Citation markers remain raw" in warning for warning in result.warnings
    )


def test_nsf_review_pdf_excludes_individual_portal_field_sections(
    make_grant, simple_config, monkeypatch
):
    captured = _install_fake_weasyprint(monkeypatch)
    config = dict(simple_config)
    config["pack"] = "nsf-pappg"
    config["funder"] = "National Science Foundation"
    config["sections"] = [
        *config["sections"],
        {
            "id": "dmsp_fields",
            "title": "Data Management and Sharing Plan",
            "file": "responses/dmsp_fields.md",
            "format": "fields",
            "required": True,
        },
    ]
    root = make_grant(
        config,
        {
            "responses/summary.md": "Summary body.",
            "responses/narrative.md": "Narrative body.",
            "responses/dmsp_fields.md": "PORTAL-FIELD-ONLY-CONTENT",
        },
    )

    build_project(GrantProject(root), fmt="pdf")

    assert "PORTAL-FIELD-ONLY-CONTENT" not in captured["html"]
    assert "Data Management and Sharing Plan" not in captured["html"]


def test_non_nsf_pdf_keeps_existing_generic_document_style(
    make_grant, simple_config, monkeypatch
):
    captured = _install_fake_weasyprint(monkeypatch)
    root = make_grant(
        simple_config,
        {
            "responses/summary.md": "Summary body.",
            "responses/narrative.md": "Narrative body.",
        },
    )

    result = build_project(GrantProject(root), fmt="pdf")

    assert "Georgia" in captured["html"]
    assert "Segoe UI" in captured["html"]
    assert "NOT FOR NSF SUBMISSION" not in captured["html"]
    assert result.warnings == []


def test_cli_surfaces_nsf_review_and_raw_citation_warnings(
    make_grant, simple_config, monkeypatch
):
    _install_fake_weasyprint(monkeypatch)
    root, _ = _nsf_project(make_grant, simple_config)

    result = CliRunner().invoke(main, ["build", "--format", "pdf", str(root)])

    assert result.exit_code == 0
    assert "Build complete" in result.stdout
    stderr = " ".join(result.stderr.split())
    assert "combined review copies only" in stderr
    assert "upload or enter each required section separately" in stderr
    assert "Citation markers remain raw" in stderr


def test_build_help_calls_nsf_pdf_review_only():
    result = CliRunner().invoke(main, ["build", "--help"])

    assert result.exit_code == 0
    assert "NSF PDFs are review-only" in " ".join(result.output.split())

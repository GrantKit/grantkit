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

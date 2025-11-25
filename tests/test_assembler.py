"""Tests for core document assembly functionality."""

import tempfile
from pathlib import Path

import pytest
import yaml

from grantkit.core.assembler import (
    AssemblyResult,
    GrantAssembler,
    SectionInfo,
)


class TestSectionInfo:
    """Tests for SectionInfo dataclass."""

    def test_defaults(self):
        """Should have sensible defaults."""
        section = SectionInfo(id="test", title="Test Section")
        assert section.id == "test"
        assert section.title == "Test Section"
        assert section.file_path is None
        assert section.page_limit is None
        assert section.word_limit is None
        assert section.required is True
        assert section.content == ""
        assert section.word_count == 0
        assert section.is_complete is False

    def test_with_limits(self):
        """Should store page and word limits."""
        section = SectionInfo(
            id="desc",
            title="Project Description",
            page_limit=15,
            word_limit=3750,
        )
        assert section.page_limit == 15
        assert section.word_limit == 3750


class TestAssemblyResult:
    """Tests for AssemblyResult dataclass."""

    def test_defaults(self):
        """Should initialize lists to empty."""
        result = AssemblyResult(success=True)
        assert result.success is True
        assert result.sections == []
        assert result.warnings == []
        assert result.errors == []

    def test_with_sections(self):
        """Should store sections list."""
        sections = [SectionInfo(id="1", title="Section 1")]
        result = AssemblyResult(success=True, sections=sections)
        assert len(result.sections) == 1


class TestGrantAssembler:
    """Tests for GrantAssembler class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory with config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create grant.yaml config
            config = {
                "title": "Test Grant",
                "pi": "Test PI",
                "sections": [
                    {
                        "id": "summary",
                        "title": "Project Summary",
                        "file": "responses/summary.md",
                        "word_limit": 300,
                        "required": True,
                    },
                    {
                        "id": "description",
                        "title": "Project Description",
                        "file": "responses/description.md",
                        "page_limit": 15,
                        "required": True,
                    },
                    {
                        "id": "references",
                        "title": "References",
                        "file": "responses/references.md",
                        "required": False,
                    },
                ],
            }
            config_path = project_root / "grant.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            # Create response files
            responses_dir = project_root / "responses"
            responses_dir.mkdir()

            (responses_dir / "summary.md").write_text(
                "# Project Summary\n\nThis is a test summary with enough words."
            )
            (responses_dir / "description.md").write_text(
                "# Project Description\n\n" + "Word " * 100
            )

            yield project_root

    def test_init_loads_config(self, temp_project):
        """Should load configuration on init."""
        assembler = GrantAssembler(temp_project)
        # Use resolve() to handle macOS /var -> /private/var symlink
        assert assembler.project_root == temp_project.resolve()
        assert "title" in assembler.config

    def test_load_sections_from_config(self, temp_project):
        """Should parse sections from config."""
        assembler = GrantAssembler(temp_project)
        assembler.load_sections_from_config()

        assert len(assembler.sections) == 3
        assert assembler.sections[0].id == "summary"
        assert assembler.sections[0].word_limit == 300
        assert assembler.sections[1].page_limit == 15

    def test_load_section_content(self, temp_project):
        """Should load content and count words."""
        assembler = GrantAssembler(temp_project)
        assembler.load_sections_from_config()

        section = assembler.sections[0]  # summary
        assembler.load_section_content(section)

        assert section.is_complete is True
        assert section.word_count > 0
        assert "Project Summary" in section.content

    def test_load_all_content(self, temp_project):
        """Should load all sections."""
        assembler = GrantAssembler(temp_project)
        assembler.load_all_content()

        complete = [s for s in assembler.sections if s.is_complete]
        assert len(complete) == 2  # summary and description

    def test_assemble_document(self, temp_project):
        """Should assemble document successfully."""
        assembler = GrantAssembler(temp_project)
        result = assembler.assemble_document()

        assert result.success is True
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.total_words > 0

    def test_assemble_tracks_missing_required(self, temp_project):
        """Should track missing required sections."""
        # Remove the description file
        (temp_project / "responses" / "description.md").unlink()

        assembler = GrantAssembler(temp_project)
        result = assembler.assemble_document()

        # Should still succeed but have errors for missing section
        assert any("missing" in e.lower() for e in result.errors)

    def test_get_completion_status(self, temp_project):
        """Should return completion statistics."""
        assembler = GrantAssembler(temp_project)
        status = assembler.get_completion_status()

        assert status["total_sections"] == 3
        assert status["complete_sections"] == 2
        assert status["completion_percentage"] > 0
        assert "sections" in status

    def test_validate_proposal(self, temp_project):
        """Should detect validation issues."""
        assembler = GrantAssembler(temp_project)
        assembler.load_all_content()
        issues = assembler.validate_proposal()

        # References section is missing but not required
        assert isinstance(issues, list)

    def test_generate_table_of_contents(self, temp_project):
        """Should generate TOC from complete sections."""
        assembler = GrantAssembler(temp_project)
        assembler.load_all_content()
        toc = assembler.generate_table_of_contents()

        assert "Table of Contents" in toc
        assert "Project Summary" in toc

    def test_word_limit_warning(self, temp_project):
        """Should warn when section exceeds word limit."""
        # Write content that exceeds 300 word limit
        (temp_project / "responses" / "summary.md").write_text("Word " * 500)

        assembler = GrantAssembler(temp_project)
        result = assembler.assemble_document()

        assert any("word limit" in w.lower() for w in result.warnings)


class TestAssemblerEdgeCases:
    """Edge case tests for GrantAssembler."""

    def test_no_config_file(self):
        """Should handle missing config gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assembler = GrantAssembler(Path(tmpdir))
            assert assembler.config == {}

    def test_empty_sections(self):
        """Should handle empty sections list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            config = {"title": "Test", "sections": []}
            with open(project_root / "grant.yaml", "w") as f:
                yaml.dump(config, f)

            assembler = GrantAssembler(project_root)
            assembler.load_sections_from_config()
            assert assembler.sections == []

    def test_funder_specific_sections(self):
        """Should support funder-specific section configs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            config = {
                "nsf": {
                    "sections": [
                        {"id": "summary", "title": "Summary", "file": "s.md"}
                    ]
                }
            }
            with open(project_root / "grant.yaml", "w") as f:
                yaml.dump(config, f)

            assembler = GrantAssembler(project_root)
            assembler.load_sections_from_config()
            assert len(assembler.sections) == 1

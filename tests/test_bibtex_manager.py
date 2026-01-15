"""Tests for BibTeX manager functionality."""

import pytest
from pathlib import Path
from grantkit.references.bibtex_manager import BibTeXManager


class TestParseAuthors:
    """Tests for author parsing, especially corporate/institutional authors."""

    def test_corporate_author_double_braces(self, tmp_path):
        """Corporate authors with {{Name}} should be preserved as full name."""
        bib_content = """
@misc{stroud_ctr_2025,
  author = {{Stroud District Council}},
  title = {Council Tax Rates},
  year = {2025}
}
"""
        bib_file = tmp_path / "references.bib"
        bib_file.write_text(bib_content)

        manager = BibTeXManager(tmp_path)
        manager.load_bibliography(bib_file)

        entry = manager.get_entry("stroud_ctr_2025")
        assert entry is not None
        assert entry.authors == ["Stroud District Council"]

    def test_multiple_corporate_authors(self, tmp_path):
        """Multiple corporate authors should both be preserved."""
        bib_content = """
@misc{stroud_ctr_2025,
  author = {{Stroud District Council}},
  title = {Stroud Tax},
  year = {2025}
}

@misc{dudley_ctr_2025,
  author = {{Dudley Metropolitan Borough Council}},
  title = {Dudley Tax},
  year = {2025}
}
"""
        bib_file = tmp_path / "references.bib"
        bib_file.write_text(bib_content)

        manager = BibTeXManager(tmp_path)
        manager.load_bibliography(bib_file)

        stroud = manager.get_entry("stroud_ctr_2025")
        dudley = manager.get_entry("dudley_ctr_2025")

        assert stroud.authors == ["Stroud District Council"]
        assert dudley.authors == ["Dudley Metropolitan Borough Council"]

    def test_regular_author_last_first(self, tmp_path):
        """Regular authors in 'Last, First' format."""
        bib_content = """
@article{smith2024,
  author = {Smith, John},
  title = {A Paper},
  year = {2024}
}
"""
        bib_file = tmp_path / "references.bib"
        bib_file.write_text(bib_content)

        manager = BibTeXManager(tmp_path)
        manager.load_bibliography(bib_file)

        entry = manager.get_entry("smith2024")
        assert entry.authors == ["Smith, John"]

    def test_multiple_regular_authors(self, tmp_path):
        """Multiple regular authors separated by 'and'."""
        bib_content = """
@article{smith2024,
  author = {Smith, John and Jones, Jane},
  title = {A Paper},
  year = {2024}
}
"""
        bib_file = tmp_path / "references.bib"
        bib_file.write_text(bib_content)

        manager = BibTeXManager(tmp_path)
        manager.load_bibliography(bib_file)

        entry = manager.get_entry("smith2024")
        assert entry.authors == ["Smith, John", "Jones, Jane"]

    def test_mixed_corporate_and_regular_authors(self, tmp_path):
        """Mix of corporate and regular authors."""
        bib_content = """
@report{mixed2024,
  author = {{World Health Organization} and Smith, John},
  title = {Health Report},
  year = {2024}
}
"""
        bib_file = tmp_path / "references.bib"
        bib_file.write_text(bib_content)

        manager = BibTeXManager(tmp_path)
        manager.load_bibliography(bib_file)

        entry = manager.get_entry("mixed2024")
        assert entry.authors == ["World Health Organization", "Smith, John"]

    def test_corporate_author_with_and_in_name(self, tmp_path):
        """Corporate author containing 'and' in name should not be split."""
        bib_content = """
@misc{mhclg2024,
  author = {{Ministry of Housing, Communities and Local Government}},
  title = {Council Tax Statistics},
  year = {2024}
}
"""
        bib_file = tmp_path / "references.bib"
        bib_file.write_text(bib_content)

        manager = BibTeXManager(tmp_path)
        manager.load_bibliography(bib_file)

        entry = manager.get_entry("mhclg2024")
        assert entry.authors == ["Ministry of Housing, Communities and Local Government"]

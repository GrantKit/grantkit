"""BibTeX file management and parsing functionality."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from pylatexenc.latex2text import LatexNodes2Text

logger = logging.getLogger(__name__)


@dataclass
class BibEntry:
    """Represents a bibliography entry."""

    key: str
    entry_type: str
    title: str
    authors: List[str]
    year: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    raw_entry: Dict[str, Any] = None

    def __post_init__(self):
        if self.raw_entry is None:
            self.raw_entry = {}


class BibTeXManager:
    """Manages BibTeX files and bibliography entries."""

    def __init__(self, project_root: Path):
        """Initialize BibTeX manager for a project.

        Args:
            project_root: Root directory of the grant project
        """
        self.project_root = Path(project_root)
        self.bibtex_files: List[Path] = []
        self.entries: Dict[str, BibEntry] = {}
        self.latex_converter = LatexNodes2Text()

        # Configure bibtexparser
        self.parser = BibTexParser(common_strings=True)
        self.parser.ignore_nonstandard_types = False
        self.parser.homogenise_fields = True

        self.writer = BibTexWriter()
        self.writer.indent = "  "
        self.writer.order_entries_by = "id"

        # Auto-discover .bib files
        self._discover_bibtex_files()

    def _discover_bibtex_files(self) -> None:
        """Discover .bib files in the project directory."""
        # Common locations for bibliography files
        search_paths = [
            self.project_root,
            self.project_root / "references",
            self.project_root / "bibliography",
            self.project_root / "docs",
            self.project_root / "sections",
        ]

        for search_path in search_paths:
            if search_path.exists():
                bib_files = list(search_path.glob("*.bib"))
                self.bibtex_files.extend(bib_files)

        # Remove duplicates
        self.bibtex_files = list(set(self.bibtex_files))

        if self.bibtex_files:
            logger.info(
                f"Found {len(self.bibtex_files)} BibTeX files: {[f.name for f in self.bibtex_files]}"
            )
        else:
            logger.info("No BibTeX files found in project directory")

    def load_bibliography(self, bib_file: Optional[Path] = None) -> None:
        """Load bibliography entries from BibTeX file(s).

        Args:
            bib_file: Specific .bib file to load, or None to load all discovered files
        """
        files_to_load = [bib_file] if bib_file else self.bibtex_files

        for bib_path in files_to_load:
            if not bib_path.exists():
                logger.warning(f"BibTeX file not found: {bib_path}")
                continue

            try:
                with open(bib_path, "r", encoding="utf-8") as bib_file_obj:
                    database = bibtexparser.load(bib_file_obj, self.parser)

                logger.info(
                    f"Loaded {len(database.entries)} entries from {bib_path.name}"
                )

                for entry in database.entries:
                    bib_entry = self._parse_bibtex_entry(entry)
                    self.entries[bib_entry.key] = bib_entry

            except Exception as e:
                logger.error(f"Failed to load BibTeX file {bib_path}: {e}")

    def _parse_bibtex_entry(self, entry: Dict[str, str]) -> BibEntry:
        """Parse a raw BibTeX entry into a BibEntry object."""
        # Extract and clean LaTeX formatting from title and other fields
        title = self._clean_latex(entry.get("title", ""))

        # Parse authors
        authors_raw = entry.get("author", "")
        authors = self._parse_authors(authors_raw)

        return BibEntry(
            key=entry["ID"],
            entry_type=entry["ENTRYTYPE"],
            title=title,
            authors=authors,
            year=entry.get("year"),
            journal=self._clean_latex(entry.get("journal", "")),
            volume=entry.get("volume"),
            pages=entry.get("pages"),
            doi=entry.get("doi"),
            url=entry.get("url"),
            raw_entry=entry,
        )

    def _clean_latex(self, text: str) -> str:
        """Clean LaTeX formatting from text."""
        if not text:
            return text

        try:
            # Convert LaTeX to plain text
            cleaned = self.latex_converter.latex_to_text(text)
            # Remove extra braces that might remain
            cleaned = re.sub(r"[{}]", "", cleaned)
            return cleaned.strip()
        except Exception as e:
            logger.warning(f"Failed to clean LaTeX from text '{text}': {e}")
            # Fallback: simple brace removal
            return re.sub(r"[{}]", "", text).strip()

    def _parse_authors(self, authors_raw: str) -> List[str]:
        """Parse author string into a list of individual authors."""
        if not authors_raw:
            return []

        # Clean LaTeX
        authors_clean = self._clean_latex(authors_raw)

        # Split by 'and'
        authors = [author.strip() for author in authors_clean.split(" and ")]

        # Handle various name formats
        parsed_authors = []
        for author in authors:
            if not author:
                continue
            # For now, just clean up whitespace
            parsed_authors.append(" ".join(author.split()))

        return parsed_authors

    def get_entry(self, key: str) -> Optional[BibEntry]:
        """Get a bibliography entry by key."""
        return self.entries.get(key)

    def has_entry(self, key: str) -> bool:
        """Check if an entry exists."""
        return key in self.entries

    def get_all_keys(self) -> Set[str]:
        """Get all available citation keys."""
        return set(self.entries.keys())

    def search_entries(
        self, query: str, fields: Optional[List[str]] = None
    ) -> List[BibEntry]:
        """Search entries by query string.

        Args:
            query: Search query
            fields: Fields to search in (default: title, authors)

        Returns:
            List of matching entries
        """
        if fields is None:
            fields = ["title", "authors"]

        query_lower = query.lower()
        matches = []

        for entry in self.entries.values():
            for field in fields:
                if field == "title" and query_lower in entry.title.lower():
                    matches.append(entry)
                    break
                elif field == "authors":
                    author_text = " ".join(entry.authors).lower()
                    if query_lower in author_text:
                        matches.append(entry)
                        break

        return matches

    def validate_entries(self) -> List[str]:
        """Validate bibliography entries and return list of issues."""
        issues = []

        for key, entry in self.entries.items():
            # Check required fields based on entry type
            if entry.entry_type.lower() == "article":
                required_fields = ["title", "authors", "journal", "year"]
                for field in required_fields:
                    value = getattr(entry, field)
                    if not value or (isinstance(value, list) and not value):
                        issues.append(
                            f"Entry '{key}': Missing required field '{field}' for article"
                        )

            elif entry.entry_type.lower() == "book":
                required_fields = ["title", "authors", "year"]
                for field in required_fields:
                    value = getattr(entry, field)
                    if not value or (isinstance(value, list) and not value):
                        issues.append(
                            f"Entry '{key}': Missing required field '{field}' for book"
                        )

            # Check for suspicious URLs or DOIs
            if entry.url and not self._is_valid_url_for_nsf(entry.url):
                issues.append(
                    f"Entry '{key}': URL may not be appropriate for NSF proposal: {entry.url}"
                )

        return issues

    def _is_valid_url_for_nsf(self, url: str) -> bool:
        """Check if URL is appropriate for NSF proposals."""
        # Allow academic, institutional, and DOI URLs
        allowed_patterns = [
            r"doi\.org",
            r"\.edu",
            r"\.gov",
            r"arxiv\.org",
            r"ieee\.org",
            r"acm\.org",
            r"springer\.com",
            r"elsevier\.com",
            r"nature\.com",
            r"science\.org",
        ]

        url_lower = url.lower()
        return any(
            re.search(pattern, url_lower) for pattern in allowed_patterns
        )

    def export_used_entries(
        self, used_keys: Set[str], output_path: Path
    ) -> None:
        """Export only the used bibliography entries to a new .bib file.

        Args:
            used_keys: Set of citation keys that are actually used
            output_path: Path for the output .bib file
        """
        database = BibDatabase()
        database.entries = []

        for key in used_keys:
            if key in self.entries:
                database.entries.append(self.entries[key].raw_entry)
            else:
                logger.warning(
                    f"Used citation key '{key}' not found in bibliography"
                )

        # Sort entries by key
        database.entries.sort(key=lambda x: x["ID"])

        with open(output_path, "w", encoding="utf-8") as bib_file:
            bib_file.write(self.writer.write(database))

        logger.info(
            f"Exported {len(database.entries)} entries to {output_path}"
        )

    def create_sample_bibliography(self, output_path: Path) -> None:
        """Create a sample .bib file with common entry types."""
        sample_bib = """@article{sample_article_2024,
  title = {A Sample Research Article for NSF Proposals},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Sample Research},
  volume = {42},
  number = {1},
  pages = {1--15},
  year = {2024},
  doi = {10.1000/sample.doi},
  url = {https://doi.org/10.1000/sample.doi}
}

@book{sample_book_2023,
  title = {Foundations of Sample Research},
  author = {Brown, Alice},
  publisher = {Academic Press},
  year = {2023},
  isbn = {978-0-123456-78-9}
}

@inproceedings{sample_conference_2024,
  title = {Innovative Approaches in Sample Science},
  author = {Johnson, Bob and Wilson, Carol},
  booktitle = {Proceedings of the International Sample Conference},
  pages = {123--130},
  year = {2024},
  organization = {IEEE}
}

@misc{sample_software_2024,
  title = {SampleTool: An Open-Source Research Platform},
  author = {Taylor, David},
  year = {2024},
  url = {https://github.com/example/sampletool},
  note = {Version 2.1}
}"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(sample_bib)

        logger.info(f"Created sample bibliography at {output_path}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the loaded bibliography."""
        if not self.entries:
            return {}

        entry_types = {}
        years = []

        for entry in self.entries.values():
            # Count entry types
            entry_type = entry.entry_type.lower()
            entry_types[entry_type] = entry_types.get(entry_type, 0) + 1

            # Collect years
            if entry.year:
                try:
                    years.append(int(entry.year))
                except ValueError:
                    pass

        return {
            "total_entries": len(self.entries),
            "entry_types": entry_types,
            "year_range": (min(years), max(years)) if years else None,
            "files_loaded": len(self.bibtex_files),
        }

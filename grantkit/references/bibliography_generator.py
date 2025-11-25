"""Generate formatted bibliographies for NSF proposals."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from .bibtex_manager import BibTeXManager
from .citation_extractor import CitationExtractor, CitationReport
from .nsf_styles import NSFBibliographyFormatter, NSFCitationStyle

logger = logging.getLogger(__name__)


@dataclass
class BibliographyResult:
    """Result of bibliography generation."""

    success: bool
    bibliography_content: str = ""
    citation_order: List[str] = None
    references_count: int = 0
    warnings: List[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.citation_order is None:
            self.citation_order = []
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


class BibliographyGenerator:
    """Generates NSF-compliant bibliographies from BibTeX and citations."""

    def __init__(self, project_root: Path, style: NSFCitationStyle = None):
        """Initialize bibliography generator.

        Args:
            project_root: Root directory of the project
            style: Citation style configuration
        """
        self.project_root = Path(project_root)
        self.style = style or NSFCitationStyle()
        self.bibtex_manager = BibTeXManager(project_root)
        self.citation_extractor = CitationExtractor()
        self.formatter = NSFBibliographyFormatter(self.style)

    def generate_complete_bibliography(
        self, content_directory: Path = None, output_path: Path = None
    ) -> BibliographyResult:
        """Generate a complete bibliography from project content.

        Args:
            content_directory: Directory containing content files (default: project root)
            output_path: Where to save the bibliography (optional)

        Returns:
            BibliographyResult with generated bibliography
        """
        if content_directory is None:
            content_directory = self.project_root

        result = BibliographyResult(success=False)

        try:
            # Load bibliography entries
            self.bibtex_manager.load_bibliography()
            if not self.bibtex_manager.entries:
                result.warnings.append("No BibTeX entries found")

            # Extract citations from content
            citation_report = self.citation_extractor.generate_citation_report(
                content_directory, self.bibtex_manager.get_all_keys()
            )

            # Validate citations
            if citation_report.missing_entries:
                for key in citation_report.missing_entries:
                    result.errors.append(
                        f"Citation key '{key}' not found in bibliography"
                    )

            if citation_report.unused_entries:
                result.warnings.append(
                    f"{len(citation_report.unused_entries)} bibliography entries are unused"
                )

            # Determine citation order
            citation_order = self._determine_citation_order(citation_report)

            # Generate bibliography
            bibliography_content = self._generate_bibliography_content(
                citation_order
            )

            result.success = len(result.errors) == 0
            result.bibliography_content = bibliography_content
            result.citation_order = citation_order
            result.references_count = len(citation_order)

            # Save if requested
            if output_path and result.success:
                self._save_bibliography(bibliography_content, output_path)

        except Exception as e:
            result.errors.append(f"Bibliography generation failed: {str(e)}")
            logger.error(f"Bibliography generation error: {e}")

        return result

    def generate_references_section(self, used_citations: List[str]) -> str:
        """Generate a references section with only the used citations.

        Args:
            used_citations: List of citation keys that were actually used

        Returns:
            Formatted references section as markdown
        """
        # Load bibliography
        self.bibtex_manager.load_bibliography()

        # Filter to used citations and sort
        available_citations = [
            key for key in used_citations if key in self.bibtex_manager.entries
        ]

        # Sort according to style
        citation_order = self._sort_citations(available_citations)

        # Generate content
        content = self._generate_bibliography_content(citation_order)

        return content

    def _determine_citation_order(
        self, citation_report: CitationReport
    ) -> List[str]:
        """Determine the order of citations for the bibliography."""
        available_keys = [
            key
            for key in citation_report.citation_keys
            if key in self.bibtex_manager.entries
        ]

        return self._sort_citations(available_keys)

    def _sort_citations(self, citation_keys: List[str]) -> List[str]:
        """Sort citation keys according to the style."""
        if not citation_keys:
            return []

        if self.style.sort_order == "alphabetical":
            # Sort alphabetically by first author's last name
            def get_sort_key(key: str) -> str:
                entry = self.bibtex_manager.get_entry(key)
                if entry and entry.authors:
                    # Extract last name of first author
                    first_author = entry.authors[0]
                    if "," in first_author:
                        return first_author.split(",")[0].strip().lower()
                    else:
                        # Assume "First Last" format
                        parts = first_author.split()
                        return parts[-1].lower() if parts else key.lower()
                return key.lower()

            return sorted(citation_keys, key=get_sort_key)
        else:
            # Keep order of citation (would need order information from extractor)
            return sorted(citation_keys)  # Fallback to alphabetical

    def _generate_bibliography_content(self, citation_order: List[str]) -> str:
        """Generate the formatted bibliography content."""
        if not citation_order:
            return "## References Cited\n\nNo references found.\n"

        lines = ["## References Cited\n"]

        for i, key in enumerate(citation_order, 1):
            entry = self.bibtex_manager.get_entry(key)
            if entry:
                formatted_entry = self.formatter.format_entry(entry, i)
                lines.append(formatted_entry)
            else:
                lines.append(f"[{i}] **Missing entry: {key}**")

        return "\n\n".join(lines) + "\n"

    def _save_bibliography(self, content: str, output_path: Path) -> None:
        """Save bibliography to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Bibliography saved to {output_path}")

    def process_content_with_citations(
        self, content: str
    ) -> Tuple[str, List[str]]:
        """Process content to replace citations and extract used keys.

        Args:
            content: The content with citations

        Returns:
            Tuple of (processed_content, used_citation_keys)
        """
        # Extract citations
        citations = self.citation_extractor.extract_citations_from_text(
            content
        )
        used_keys = list(set(c.citation_key for c in citations))

        # Sort the keys for consistent numbering
        sorted_keys = self._sort_citations(used_keys)

        # Replace citations with numbers
        processed_content = (
            self.citation_extractor.replace_citations_with_numbers(
                content, sorted_keys
            )
        )

        return processed_content, sorted_keys

    def create_separate_references_document(
        self, main_content: str, output_path: Path = None
    ) -> BibliographyResult:
        """Create a separate references document from main content.

        This ensures references don't count toward page limits.

        Args:
            main_content: The main proposal content
            output_path: Where to save the references document

        Returns:
            BibliographyResult with the references document
        """
        result = BibliographyResult(success=False)

        try:
            # Load bibliography
            self.bibtex_manager.load_bibliography()

            # Extract citations from main content
            citations = self.citation_extractor.extract_citations_from_text(
                main_content
            )
            used_keys = list(set(c.citation_key for c in citations))

            # Validate citations
            missing_keys = [
                key
                for key in used_keys
                if key not in self.bibtex_manager.entries
            ]

            if missing_keys:
                for key in missing_keys:
                    result.errors.append(
                        f"Citation key '{key}' not found in bibliography"
                    )

            # Generate references section
            available_keys = [
                key for key in used_keys if key in self.bibtex_manager.entries
            ]
            citation_order = self._sort_citations(available_keys)

            bibliography_content = self._generate_bibliography_content(
                citation_order
            )

            result.success = len(result.errors) == 0
            result.bibliography_content = bibliography_content
            result.citation_order = citation_order
            result.references_count = len(citation_order)

            # Save if requested
            if output_path and result.success:
                self._save_bibliography(bibliography_content, output_path)

        except Exception as e:
            result.errors.append(
                f"References document generation failed: {str(e)}"
            )
            logger.error(f"References document error: {e}")

        return result

    def get_citation_statistics(self) -> Dict[str, any]:
        """Get statistics about citations and bibliography."""
        self.bibtex_manager.load_bibliography()

        # Get project citation report
        citation_report = self.citation_extractor.generate_citation_report(
            self.project_root, self.bibtex_manager.get_all_keys()
        )

        # Get bibliography statistics
        bib_stats = self.bibtex_manager.get_statistics()

        return {
            "bibliography": bib_stats,
            "citations": {
                "total_citations": citation_report.total_citations,
                "unique_citations": citation_report.unique_citations,
                "missing_entries": len(citation_report.missing_entries),
                "unused_entries": len(citation_report.unused_entries),
                "files_with_citations": len(citation_report.citations_by_file),
            },
        }

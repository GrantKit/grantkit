"""Generate formatted bibliographies for NSF proposals.

Numbering contract: a proposal's documents (Project Summary, Project
Description, References Cited, ...) must all be numbered from ONE key list.
Build it once with :meth:`BibliographyGenerator.citation_order` over every
document, then pass it as ``citation_order`` to each per-document call, or
use :meth:`BibliographyGenerator.process_documents_with_citations`. Numbering
a document on its own numbers only the keys that document cites, so a
Summary citing a subset gets different numbers from the Description.

The order itself is a pure function of the keys and the .bib contents: it
never depends on set iteration order, so it is the same in every process
whatever ``PYTHONHASHSEED`` is.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .bibtex_manager import BibEntry, BibTeXManager
from .citation_extractor import CitationExtractor, CitationReport
from .nsf_styles import NSFBibliographyFormatter, NSFCitationStyle

logger = logging.getLogger(__name__)

SortName = Tuple[str, str]


def _sort_name(author: str, corporate: bool) -> SortName:
    """Return ``(surname, given names)``, casefolded, for sorting.

    A corporate author is sorted by its whole name ("National Science
    Foundation" under N), as BibTeX does for a brace-protected name.
    """
    if corporate:
        return (author.casefold(), "")
    if "," in author:
        surname, given = author.split(",", 1)
        return (surname.strip().casefold(), given.strip().casefold())
    # Assume "First Last" format
    parts = author.split()
    if not parts:
        return ("", "")
    return (parts[-1].casefold(), " ".join(parts[:-1]).casefold())


def _dedupe(keys: Iterable[str]) -> List[str]:
    """De-duplicate keys, keeping first-appearance order.

    Unlike ``list(set(keys))``, the result does not depend on the
    per-process string-hash seed.
    """
    return list(dict.fromkeys(keys))


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

        Numbered the same way as :meth:`process_content_with_citations`
        numbers text citing the same keys: a key missing from the .bib keeps
        its number and gets a "Missing entry" line rather than being dropped,
        which would shift every later number.

        Args:
            used_citations: List of citation keys that were actually used

        Returns:
            Formatted references section as markdown
        """
        # Load bibliography
        self.bibtex_manager.load_bibliography()

        # Sort according to style
        citation_order = self._sort_citations(used_citations)

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

    def _sort_citations(self, citation_keys: Iterable[str]) -> List[str]:
        """Sort citation keys according to the style.

        Duplicates are dropped. The order is total: two distinct keys never
        compare equal, so the result never depends on the input order.
        """
        keys = _dedupe(citation_keys)
        if not keys:
            return []

        if self.style.sort_order == "alphabetical":
            return sorted(keys, key=self._alphabetical_sort_key)
        else:
            # Keep order of citation (would need order information from extractor)
            return sorted(keys)  # Fallback to alphabetical by key

    def _alphabetical_sort_key(
        self, key: str
    ) -> Tuple[str, Tuple[SortName, ...], str, str, str]:
        """Sort key: first author's surname, then a total tie-break.

        Ties on the surname (several entries by one organization, say) are
        broken by the full author list, year, and title, and finally by the
        citation key itself, which is unique.
        """
        entry: Optional[BibEntry] = self.bibtex_manager.get_entry(key)
        if entry is None:
            return (key.casefold(), (), "", "", key)
        names = tuple(
            _sort_name(author, author in entry.corporate_authors)
            for author in entry.authors
        )
        surname = names[0][0] if names else key.casefold()
        return (
            surname,
            names,
            (entry.year or "").casefold(),
            (entry.title or "").casefold(),
            key,
        )

    def citation_order(self, documents: Iterable[str]) -> List[str]:
        """Return the one numbering order shared by a proposal's documents.

        Collects every citation key from every document and sorts the union
        by the style. Number each document with this list (``[n]`` is
        ``order[n - 1]``) and build References Cited from it, so a key has
        the same number everywhere.

        Keys absent from the .bib are included (they get a number, and a
        "Missing entry" line in References Cited) so numbering never shifts.

        Args:
            documents: The text of each document, e.g.
                ``[summary, description]``. A bare string is one document.

        Returns:
            Citation keys in numbering order.
        """
        if isinstance(documents, str):
            documents = [documents]
        # The sort reads authors, years and titles from the .bib; without
        # them every key would sort by its own name.
        self.bibtex_manager.load_bibliography()
        keys = [
            citation.citation_key
            for document in documents
            for citation in self.citation_extractor.extract_citations_from_text(
                document
            )
        ]
        return self._sort_citations(keys)

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
        self, content: str, citation_order: Optional[Sequence[str]] = None
    ) -> Tuple[str, List[str]]:
        """Replace ``[@key]`` citations in one document with ``[n]`` numbers.

        For a proposal with more than one document (Summary + Description),
        pass the shared ``citation_order`` from :meth:`citation_order`. When
        it is omitted, the document is numbered from only the keys it cites,
        which gives a different numbering from any other document that
        cites a different set of keys.

        Args:
            content: The content with citations
            citation_order: The shared numbering order. Every key the
                content cites must be in it.

        Returns:
            Tuple of (processed_content, citation_order): the order the
            numbers index into (``[n]`` is ``citation_order[n - 1]``).

        Raises:
            ValueError: If ``content`` cites a key missing from
                ``citation_order``.
        """
        if citation_order is None:
            order = self.citation_order([content])
        else:
            order = list(citation_order)
            self._require_keys_in_order(content, order)

        processed_content = (
            self.citation_extractor.replace_citations_with_numbers(
                content, order
            )
        )

        return processed_content, order

    def process_documents_with_citations(
        self, documents: Sequence[str]
    ) -> Tuple[List[str], List[str]]:
        """Number several documents of one proposal from one shared order.

        Args:
            documents: The text of each document, e.g.
                ``[summary, description]``.

        Returns:
            Tuple of (processed documents in input order, citation_order).
            Build References Cited from the same ``citation_order``, e.g.
            ``create_separate_references_document(
            "\\n".join(documents), citation_order=citation_order)``.
        """
        if isinstance(documents, str):
            documents = [documents]
        order = self.citation_order(documents)
        processed = [
            self.citation_extractor.replace_citations_with_numbers(
                document, order
            )
            for document in documents
        ]
        return processed, order

    def _require_keys_in_order(self, content: str, order: List[str]) -> None:
        """Raise if ``content`` cites a key the shared order doesn't hold.

        Such a key would be left unnumbered (or silently dropped from a
        multi-key group), so fail loudly instead.
        """
        in_order = set(order)
        stray = _dedupe(
            citation.citation_key
            for citation in self.citation_extractor.extract_citations_from_text(
                content
            )
            if citation.citation_key not in in_order
        )
        if stray:
            raise ValueError(
                "Content cites keys missing from citation_order: "
                f"{', '.join(stray)}. Build the order from every document "
                "with citation_order()."
            )

    def create_separate_references_document(
        self,
        main_content: str,
        output_path: Path = None,
        citation_order: Optional[Sequence[str]] = None,
    ) -> BibliographyResult:
        """Create a separate references document from main content.

        This ensures references don't count toward page limits.

        The list is numbered exactly as :meth:`process_content_with_citations`
        numbers the text given the same ``citation_order`` (or the same
        content): a key missing from the .bib keeps its number and gets a
        "Missing entry" line, and is reported as an error.

        Args:
            main_content: The main proposal content, with ``[@key]``
                citations (not the already-numbered text)
            output_path: Where to save the references document
            citation_order: The shared numbering order from
                :meth:`citation_order`, for a multi-document proposal

        Returns:
            BibliographyResult with the references document
        """
        result = BibliographyResult(success=False)

        try:
            # Load bibliography
            self.bibtex_manager.load_bibliography()

            if citation_order is None:
                citation_order = self.citation_order([main_content])
            else:
                citation_order = list(citation_order)
                self._require_keys_in_order(main_content, citation_order)

            # Validate citations
            missing_keys = [
                key
                for key in citation_order
                if key not in self.bibtex_manager.entries
            ]

            if missing_keys:
                for key in missing_keys:
                    result.errors.append(
                        f"Citation key '{key}' not found in bibliography"
                    )

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

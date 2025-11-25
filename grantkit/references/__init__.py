"""References and BibTeX management for NSF grant proposals."""

from .bibliography_generator import BibliographyGenerator
from .bibtex_manager import BibTeXManager
from .citation_extractor import CitationExtractor
from .config import ReferencesConfig
from .nsf_styles import NSFCitationStyle

__all__ = [
    "BibTeXManager",
    "CitationExtractor",
    "BibliographyGenerator",
    "NSFCitationStyle",
    "ReferencesConfig",
]

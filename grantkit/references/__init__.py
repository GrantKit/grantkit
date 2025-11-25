"""References and BibTeX management for NSF grant proposals."""

from .bibtex_manager import BibTeXManager
from .citation_extractor import CitationExtractor
from .bibliography_generator import BibliographyGenerator
from .nsf_styles import NSFCitationStyle
from .config import ReferencesConfig

__all__ = [
    'BibTeXManager',
    'CitationExtractor', 
    'BibliographyGenerator',
    'NSFCitationStyle',
    'ReferencesConfig'
]
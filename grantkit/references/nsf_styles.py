"""NSF-compliant citation and bibliography styles."""

import re
from typing import List, Optional
from dataclasses import dataclass

from .bibtex_manager import BibEntry


@dataclass
class NSFCitationStyle:
    """NSF citation style configuration."""
    
    # NSF typically uses numbered citations
    style_type: str = "numeric"  # or "author-year"
    sort_order: str = "alphabetical"  # or "order_cited"
    include_doi: bool = True
    include_urls: bool = True
    max_authors: int = 10  # Show all authors up to this number
    et_al_threshold: int = 10  # Use "et al." after this many authors
    
    
class NSFBibliographyFormatter:
    """Formats bibliography entries according to NSF guidelines."""
    
    def __init__(self, style: NSFCitationStyle = None):
        """Initialize formatter with style configuration."""
        self.style = style or NSFCitationStyle()
        
    def format_entry(self, entry: BibEntry, number: Optional[int] = None) -> str:
        """Format a single bibliography entry.
        
        Args:
            entry: The bibliography entry to format
            number: Citation number (for numeric style)
            
        Returns:
            Formatted bibliography entry
        """
        if entry.entry_type.lower() == 'article':
            return self._format_article(entry, number)
        elif entry.entry_type.lower() == 'book':
            return self._format_book(entry, number) 
        elif entry.entry_type.lower() == 'inproceedings':
            return self._format_conference(entry, number)
        elif entry.entry_type.lower() in ['misc', 'online', 'software']:
            return self._format_misc(entry, number)
        else:
            # Generic format
            return self._format_generic(entry, number)
            
    def _format_article(self, entry: BibEntry, number: Optional[int]) -> str:
        """Format journal article entry."""
        parts = []
        
        # Add number prefix for numeric style
        if number is not None and self.style.style_type == "numeric":
            parts.append(f"[{number}]")
            
        # Authors
        authors_str = self._format_authors(entry.authors)
        parts.append(f"{authors_str}.")
        
        # Title
        if entry.title:
            parts.append(f'"{entry.title}."')
            
        # Journal
        if entry.journal:
            journal_part = f"*{entry.journal}*"
            
            # Add volume and pages
            if entry.volume:
                journal_part += f" {entry.volume}"
                if entry.pages:
                    journal_part += f", {self._format_pages(entry.pages)}"
            elif entry.pages:
                journal_part += f", {self._format_pages(entry.pages)}"
                
            parts.append(f"{journal_part}")
            
        # Year
        if entry.year:
            parts.append(f"({entry.year}).")
            
        # DOI or URL
        if entry.doi and self.style.include_doi:
            parts.append(f"https://doi.org/{entry.doi}")
        elif entry.url and self.style.include_urls and not entry.doi:
            parts.append(entry.url)
            
        return " ".join(parts)
        
    def _format_book(self, entry: BibEntry, number: Optional[int]) -> str:
        """Format book entry."""
        parts = []
        
        if number is not None and self.style.style_type == "numeric":
            parts.append(f"[{number}]")
            
        # Authors
        authors_str = self._format_authors(entry.authors)
        parts.append(f"{authors_str}.")
        
        # Title
        if entry.title:
            parts.append(f"*{entry.title}.*")
            
        # Publisher and year
        publisher = entry.raw_entry.get('publisher', '')
        if publisher and entry.year:
            parts.append(f"{publisher}, {entry.year}.")
        elif entry.year:
            parts.append(f"{entry.year}.")
        elif publisher:
            parts.append(f"{publisher}.")
            
        # DOI or URL
        if entry.doi and self.style.include_doi:
            parts.append(f"https://doi.org/{entry.doi}")
        elif entry.url and self.style.include_urls and not entry.doi:
            parts.append(entry.url)
            
        return " ".join(parts)
        
    def _format_conference(self, entry: BibEntry, number: Optional[int]) -> str:
        """Format conference proceedings entry."""
        parts = []
        
        if number is not None and self.style.style_type == "numeric":
            parts.append(f"[{number}]")
            
        # Authors
        authors_str = self._format_authors(entry.authors)
        parts.append(f"{authors_str}.")
        
        # Title
        if entry.title:
            parts.append(f'"{entry.title}."')
            
        # Booktitle (conference proceedings)
        booktitle = entry.raw_entry.get('booktitle', '')
        if booktitle:
            conf_part = f"*{booktitle}*"
            
            # Add pages
            if entry.pages:
                conf_part += f", {self._format_pages(entry.pages)}"
                
            parts.append(f"{conf_part}")
            
        # Organization and year
        organization = entry.raw_entry.get('organization', '')
        if organization and entry.year:
            parts.append(f"{organization}, {entry.year}.")
        elif entry.year:
            parts.append(f"{entry.year}.")
        elif organization:
            parts.append(f"{organization}.")
            
        # DOI or URL
        if entry.doi and self.style.include_doi:
            parts.append(f"https://doi.org/{entry.doi}")
        elif entry.url and self.style.include_urls and not entry.doi:
            parts.append(entry.url)
            
        return " ".join(parts)
        
    def _format_misc(self, entry: BibEntry, number: Optional[int]) -> str:
        """Format miscellaneous entry (software, websites, etc.)."""
        parts = []
        
        if number is not None and self.style.style_type == "numeric":
            parts.append(f"[{number}]")
            
        # Authors
        authors_str = self._format_authors(entry.authors)
        if authors_str:
            parts.append(f"{authors_str}.")
            
        # Title
        if entry.title:
            parts.append(f'"{entry.title}."')
            
        # Note or howpublished
        note = entry.raw_entry.get('note', '')
        howpublished = entry.raw_entry.get('howpublished', '')
        
        if note:
            parts.append(f"{note}.")
        elif howpublished:
            parts.append(f"{howpublished}.")
            
        # Year
        if entry.year:
            parts.append(f"{entry.year}.")
            
        # URL (more important for misc entries)
        if entry.url and self.style.include_urls:
            parts.append(entry.url)
            
        return " ".join(parts)
        
    def _format_generic(self, entry: BibEntry, number: Optional[int]) -> str:
        """Generic format for unknown entry types."""
        parts = []
        
        if number is not None and self.style.style_type == "numeric":
            parts.append(f"[{number}]")
            
        # Authors
        authors_str = self._format_authors(entry.authors)
        if authors_str:
            parts.append(f"{authors_str}.")
            
        # Title
        if entry.title:
            parts.append(f'"{entry.title}."')
            
        # Year
        if entry.year:
            parts.append(f"{entry.year}.")
            
        # URL or DOI as fallback
        if entry.doi and self.style.include_doi:
            parts.append(f"https://doi.org/{entry.doi}")
        elif entry.url and self.style.include_urls:
            parts.append(entry.url)
            
        return " ".join(parts)
        
    def _format_authors(self, authors: List[str]) -> str:
        """Format author list according to style guidelines."""
        if not authors:
            return ""
            
        if len(authors) == 1:
            return self._format_single_author(authors[0])
        elif len(authors) == 2:
            return f"{self._format_single_author(authors[0])} and {self._format_single_author(authors[1])}"
        elif len(authors) <= self.style.et_al_threshold:
            # Show all authors
            formatted_authors = [self._format_single_author(author) for author in authors[:-1]]
            last_author = self._format_single_author(authors[-1])
            return f"{', '.join(formatted_authors)}, and {last_author}"
        else:
            # Use et al.
            first_author = self._format_single_author(authors[0])
            return f"{first_author} et al."
            
    def _format_single_author(self, author: str) -> str:
        """Format a single author name."""
        # Handle "Last, First Middle" format
        if ',' in author:
            parts = author.split(',', 1)
            last = parts[0].strip()
            first = parts[1].strip()
            
            # Extract first name and initials
            first_parts = first.split()
            if first_parts:
                first_name = first_parts[0]
                initials = []
                for part in first_parts[1:]:
                    if len(part) == 1 or (len(part) == 2 and part.endswith('.')):
                        initials.append(part)
                    else:
                        # Another first name
                        initials.append(part[0] + '.')
                        
                if initials:
                    return f"{last}, {first_name} {' '.join(initials)}"
                else:
                    return f"{last}, {first_name}"
            else:
                return last
        else:
            # Handle "First Middle Last" format  
            parts = author.split()
            if len(parts) >= 2:
                last = parts[-1]
                first_middle = ' '.join(parts[:-1])
                return f"{last}, {first_middle}"
            else:
                return author
                
    def _format_pages(self, pages: str) -> str:
        """Format page numbers."""
        if not pages:
            return ""
            
        # Handle page ranges
        if '--' in pages:
            return pages.replace('--', '–')  # Use en-dash
        elif '-' in pages:
            # Convert hyphen to en-dash for page ranges
            if re.match(r'^\d+-\d+$', pages):
                return pages.replace('-', '–')
                
        return pages
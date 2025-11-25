"""Extract and process citations from markdown content."""

import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, NamedTuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


class CitationMatch(NamedTuple):
    """Represents a citation match in text."""
    citation_key: str
    full_match: str
    line_number: int
    column_start: int
    column_end: int


@dataclass
class CitationReport:
    """Report on citations found in content."""
    total_citations: int
    unique_citations: int
    citation_keys: Set[str]
    citations_by_file: Dict[str, List[CitationMatch]]
    missing_entries: Set[str]
    unused_entries: Set[str]
    duplicate_citations: Dict[str, int]
    

class CitationExtractor:
    """Extracts and processes citations from markdown content."""
    
    # Citation patterns - supports various formats
    CITATION_PATTERNS = [
        # Standard pandoc-style: [@key], [@key1; @key2], [@key, p. 42]
        r'\[@([^]]+)\]',
        # Alternative bracket style: [key]
        r'\[([a-zA-Z][a-zA-Z0-9_:-]*)\](?!\()',  # Not followed by ( to avoid markdown links
        # LaTeX-style: \cite{key}
        r'\\cite\{([^}]+)\}',
        # Multiple citations: \cite{key1,key2}
        r'\\citep?\{([^}]+)\}',
    ]
    
    def __init__(self):
        """Initialize the citation extractor."""
        self.compiled_patterns = [re.compile(pattern, re.MULTILINE) for pattern in self.CITATION_PATTERNS]
        
    def extract_citations_from_text(self, content: str, source_name: str = "content") -> List[CitationMatch]:
        """Extract all citations from a text string.
        
        Args:
            content: The text content to search
            source_name: Name of the source (for reporting)
            
        Returns:
            List of CitationMatch objects
        """
        citations = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in self.compiled_patterns:
                for match in pattern.finditer(line):
                    citation_text = match.group(1)
                    
                    # Parse multiple citations (separated by ; or ,)
                    citation_keys = self._parse_citation_keys(citation_text)
                    
                    for key in citation_keys:
                        if key:  # Skip empty keys
                            citations.append(CitationMatch(
                                citation_key=key,
                                full_match=match.group(0),
                                line_number=line_num,
                                column_start=match.start(),
                                column_end=match.end()
                            ))
                            
        return citations
        
    def extract_citations_from_file(self, file_path: Path) -> List[CitationMatch]:
        """Extract citations from a markdown file.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            List of CitationMatch objects
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.extract_citations_from_text(content, str(file_path))
        except Exception as e:
            logger.error(f"Failed to extract citations from {file_path}: {e}")
            return []
            
    def extract_citations_from_directory(self, directory: Path, 
                                       file_patterns: List[str] = None) -> Dict[str, List[CitationMatch]]:
        """Extract citations from all markdown files in a directory.
        
        Args:
            directory: Directory to search
            file_patterns: List of glob patterns to match (default: ["*.md", "*.markdown"])
            
        Returns:
            Dictionary mapping file paths to citation matches
        """
        if file_patterns is None:
            file_patterns = ["*.md", "*.markdown", "*.txt"]
            
        citations_by_file = {}
        
        for pattern in file_patterns:
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    citations = self.extract_citations_from_file(file_path)
                    if citations:
                        citations_by_file[str(file_path)] = citations
                        
        return citations_by_file
        
    def _parse_citation_keys(self, citation_text: str) -> List[str]:
        """Parse citation keys from citation text.
        
        Handles formats like:
        - "key1; key2"  
        - "key1, key2"
        - "key1; @key2"
        - "key1, p. 42"
        """
        # Remove @ symbols and clean up
        citation_text = citation_text.replace('@', '')
        
        # Split on semicolons and commas
        parts = re.split(r'[;,]', citation_text)
        
        keys = []
        for part in parts:
            part = part.strip()
            
            # Remove page references (p. 42, pp. 10-15, etc.)
            part = re.sub(r'\b(?:p\.?|pp\.?)\s*\d+(?:-\d+)?\b', '', part)
            part = part.strip()
            
            # Extract valid citation key
            # Citation keys should be alphanumeric with underscores, hyphens, colons
            key_match = re.match(r'^([a-zA-Z][a-zA-Z0-9_:-]*)$', part)
            if key_match:
                keys.append(key_match.group(1))
            elif part and not re.search(r'\s', part):  # No spaces = likely a key
                keys.append(part)
                
        return keys
        
    def generate_citation_report(self, directory: Path, 
                               bibtex_keys: Set[str] = None) -> CitationReport:
        """Generate a comprehensive report on citations in the project.
        
        Args:
            directory: Project directory to analyze
            bibtex_keys: Set of available BibTeX keys (for finding missing entries)
            
        Returns:
            CitationReport with detailed analysis
        """
        citations_by_file = self.extract_citations_from_directory(directory)
        
        all_citations = []
        for citations in citations_by_file.values():
            all_citations.extend(citations)
            
        # Count citations
        citation_keys = [c.citation_key for c in all_citations]
        unique_keys = set(citation_keys)
        
        # Find duplicates
        key_counts = defaultdict(int)
        for key in citation_keys:
            key_counts[key] += 1
        duplicate_citations = {k: v for k, v in key_counts.items() if v > 1}
        
        # Find missing and unused entries
        missing_entries = set()
        unused_entries = set()
        
        if bibtex_keys:
            missing_entries = unique_keys - bibtex_keys
            unused_entries = bibtex_keys - unique_keys
            
        return CitationReport(
            total_citations=len(all_citations),
            unique_citations=len(unique_keys),
            citation_keys=unique_keys,
            citations_by_file=citations_by_file,
            missing_entries=missing_entries,
            unused_entries=unused_entries,
            duplicate_citations=duplicate_citations
        )
        
    def replace_citations_with_numbers(self, content: str, 
                                     citation_order: List[str]) -> str:
        """Replace citation keys with numeric references.
        
        Args:
            content: The text content with citations
            citation_order: Ordered list of citation keys for numbering
            
        Returns:
            Content with citations replaced by numbers
        """
        # Create mapping from keys to numbers
        key_to_number = {key: i + 1 for i, key in enumerate(citation_order)}
        
        # Replace citations with numbers
        def replace_citation(match):
            citation_text = match.group(1)
            citation_keys = self._parse_citation_keys(citation_text)
            
            numbers = []
            for key in citation_keys:
                if key in key_to_number:
                    numbers.append(str(key_to_number[key]))
                    
            if numbers:
                if len(numbers) == 1:
                    return f"[{numbers[0]}]"
                else:
                    return f"[{', '.join(numbers)}]"
            else:
                return match.group(0)  # Keep original if no mapping found
                
        # Apply replacements for each pattern
        result = content
        for pattern in self.compiled_patterns:
            result = pattern.sub(replace_citation, result)
            
        return result
        
    def convert_to_latex_citations(self, content: str) -> str:
        """Convert markdown citations to LaTeX \\cite{} format.
        
        Args:
            content: Content with markdown citations
            
        Returns:
            Content with LaTeX citations
        """
        def replace_with_latex(match):
            citation_text = match.group(1)
            # Clean up the citation text but preserve multiple keys
            cleaned = citation_text.replace('@', '').strip()
            return f"\\cite{{{cleaned}}}"
            
        result = content
        # Only convert pandoc-style citations
        pandoc_pattern = re.compile(self.CITATION_PATTERNS[0], re.MULTILINE)
        result = pandoc_pattern.sub(replace_with_latex, result)
        
        return result
        
    def validate_citation_syntax(self, content: str) -> List[str]:
        """Validate citation syntax and return list of issues.
        
        Args:
            content: Content to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        lines = content.split('\n')
        
        # Look for malformed citations
        malformed_patterns = [
            (r'\[@[^]]*$', 'Unclosed citation bracket'),
            (r'\[[^@][^]]*\]\([^)]*\)', 'Possible markdown link mistaken for citation'),
            (r'@[a-zA-Z0-9_:-]+(?!\]|[,;])', 'Bare @ symbol without brackets'),
        ]
        
        for line_num, line in enumerate(lines, 1):
            for pattern, description in malformed_patterns:
                if re.search(pattern, line):
                    issues.append(f"Line {line_num}: {description}")
                    
        return issues
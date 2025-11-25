"""Content optimization for maximizing content within NSF page limits."""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class OptimizationSuggestion:
    """Suggestion for optimizing content to fit page limits."""
    
    type: str  # "reduce_spacing", "compress_figures", "shorten_text", etc.
    section: str
    description: str
    potential_savings_lines: float
    priority: int  # 1=high, 2=medium, 3=low
    implementation_difficulty: str  # "easy", "medium", "hard"


class ContentOptimizer:
    """Optimizes markdown content for PDF generation within page limits."""
    
    def __init__(self):
        self.lines_per_page = 54  # Approximate lines per page with 11pt font, 1" margins
        
    def analyze_content(self, markdown_content: str) -> Dict[str, any]:
        """Analyze markdown content and estimate page count."""
        lines = markdown_content.split('\n')
        
        analysis = {
            'total_lines': len(lines),
            'estimated_pages': len(lines) / self.lines_per_page,
            'sections': self._analyze_sections(markdown_content),
            'figures': self._count_figures(markdown_content),
            'tables': self._count_tables(markdown_content), 
            'references': self._count_references(markdown_content),
            'whitespace_lines': self._count_whitespace_lines(lines),
        }
        
        return analysis
    
    def suggest_optimizations(self, markdown_content: str, 
                            current_pages: float, 
                            target_pages: float) -> List[OptimizationSuggestion]:
        """Suggest optimizations to fit content within page limits."""
        suggestions = []
        
        if current_pages <= target_pages:
            return suggestions
            
        pages_to_cut = current_pages - target_pages
        lines_to_cut = pages_to_cut * self.lines_per_page
        
        # Analyze content for optimization opportunities
        analysis = self.analyze_content(markdown_content)
        
        # 1. Remove excess whitespace (easy wins)
        if analysis['whitespace_lines'] > 10:
            potential_savings = min(analysis['whitespace_lines'] * 0.7, lines_to_cut * 0.3)
            suggestions.append(OptimizationSuggestion(
                type="reduce_whitespace",
                section="Global",
                description=f"Remove excess blank lines ({int(potential_savings)} lines saved)",
                potential_savings_lines=potential_savings,
                priority=1,
                implementation_difficulty="easy"
            ))
        
        # 2. Compress figures
        if analysis['figures'] > 0:
            potential_savings = analysis['figures'] * 2  # ~2 lines saved per figure
            suggestions.append(OptimizationSuggestion(
                type="compress_figures", 
                section="Global",
                description=f"Reduce figure sizes by 10-15% ({int(potential_savings)} lines saved)",
                potential_savings_lines=potential_savings,
                priority=2,
                implementation_difficulty="easy"
            ))
        
        # 3. Optimize references (use smaller font)
        if analysis['references'] > 20:
            potential_savings = analysis['references'] * 0.2  # 20% savings with smaller font
            suggestions.append(OptimizationSuggestion(
                type="optimize_references",
                section="References",
                description=f"Use smaller font for references ({int(potential_savings)} lines saved)",
                potential_savings_lines=potential_savings,
                priority=1,
                implementation_difficulty="easy"
            ))
        
        # 4. Section-specific optimizations
        for section_name, section_data in analysis['sections'].items():
            if section_data['lines'] > 50:  # Only suggest for substantial sections
                # Suggest tightening section spacing
                potential_savings = section_data['lines'] * 0.05  # 5% savings
                suggestions.append(OptimizationSuggestion(
                    type="tighten_spacing",
                    section=section_name,
                    description=f"Reduce spacing in {section_name} ({int(potential_savings)} lines saved)",
                    potential_savings_lines=potential_savings,
                    priority=2,
                    implementation_difficulty="medium"
                ))
        
        # 5. Content reduction suggestions (last resort)
        longest_sections = sorted(analysis['sections'].items(), 
                                key=lambda x: x[1]['lines'], reverse=True)[:3]
        
        for section_name, section_data in longest_sections:
            if pages_to_cut > 2:  # Only suggest content cuts for major overages
                potential_savings = section_data['lines'] * 0.1  # 10% reduction
                suggestions.append(OptimizationSuggestion(
                    type="reduce_content",
                    section=section_name,
                    description=f"Reduce content in {section_name} by ~10% ({int(potential_savings)} lines saved)",
                    potential_savings_lines=potential_savings,
                    priority=3,
                    implementation_difficulty="hard"
                ))
        
        # Sort by priority and potential impact
        suggestions.sort(key=lambda x: (x.priority, -x.potential_savings_lines))
        return suggestions
    
    def apply_optimizations(self, markdown_content: str, 
                          optimization_types: List[str]) -> str:
        """Apply selected optimizations to markdown content."""
        optimized_content = markdown_content
        
        for opt_type in optimization_types:
            if opt_type == "reduce_whitespace":
                optimized_content = self._reduce_whitespace(optimized_content)
            elif opt_type == "compress_figures":
                optimized_content = self._compress_figures(optimized_content)
            elif opt_type == "tighten_spacing":
                optimized_content = self._tighten_spacing(optimized_content)
            elif opt_type == "optimize_references":
                optimized_content = self._optimize_references(optimized_content)
        
        return optimized_content
    
    def _analyze_sections(self, content: str) -> Dict[str, Dict]:
        """Analyze sections in the markdown content."""
        sections = {}
        current_section = "Introduction"
        current_lines = []
        
        for line in content.split('\n'):
            if line.startswith('# '):
                # Save previous section
                if current_lines:
                    sections[current_section] = {
                        'lines': len(current_lines),
                        'content': '\n'.join(current_lines)
                    }
                
                # Start new section  
                current_section = line[2:].strip()
                current_lines = [line]
            else:
                current_lines.append(line)
        
        # Don't forget the last section
        if current_lines:
            sections[current_section] = {
                'lines': len(current_lines),
                'content': '\n'.join(current_lines)
            }
        
        return sections
    
    def _count_figures(self, content: str) -> int:
        """Count figures in markdown content."""
        # Look for markdown image syntax and HTML img tags
        md_images = len(re.findall(r'!\[.*?\]\(.*?\)', content))
        html_images = len(re.findall(r'<img[^>]*>', content, re.IGNORECASE))
        return md_images + html_images
    
    def _count_tables(self, content: str) -> int:
        """Count tables in markdown content."""
        # Look for markdown table syntax
        table_rows = re.findall(r'^\|.*\|$', content, re.MULTILINE)
        # Estimate tables by dividing rows by average table size
        return len(table_rows) // 3 if table_rows else 0
    
    def _count_references(self, content: str) -> int:
        """Count references/bibliography entries."""
        # Look for numbered references, citation patterns, etc.
        numbered_refs = len(re.findall(r'^\d+\.\s', content, re.MULTILINE))
        citation_refs = len(re.findall(r'\[@\w+\]', content))  # Pandoc-style citations
        return max(numbered_refs, citation_refs)
    
    def _count_whitespace_lines(self, lines: List[str]) -> int:
        """Count blank/whitespace-only lines."""
        return sum(1 for line in lines if not line.strip())
    
    def _reduce_whitespace(self, content: str) -> str:
        """Remove excessive whitespace while preserving structure."""
        lines = content.split('\n')
        optimized_lines = []
        consecutive_blanks = 0
        
        for line in lines:
            if not line.strip():
                consecutive_blanks += 1
                # Only keep first blank line in a series
                if consecutive_blanks == 1:
                    optimized_lines.append(line)
            else:
                consecutive_blanks = 0
                optimized_lines.append(line)
        
        return '\n'.join(optimized_lines)
    
    def _compress_figures(self, content: str) -> str:
        """Add figure scaling directives."""
        # Add width constraints to markdown images
        content = re.sub(
            r'!\[(.*?)\]\((.*?)\)',
            r'![\1](\2){width=90%}',
            content
        )
        
        # Add HTML width attributes
        content = re.sub(
            r'<img([^>]*?)>',
            r'<img\1 style="width: 90%; height: auto;">',
            content,
            flags=re.IGNORECASE
        )
        
        return content
    
    def _tighten_spacing(self, content: str) -> str:
        """Reduce spacing around sections and lists."""
        # This would be handled more by LaTeX template adjustments
        # For markdown, we can remove extra spacing around headers
        lines = content.split('\n')
        optimized_lines = []
        
        for i, line in enumerate(lines):
            optimized_lines.append(line)
            
            # Don't add extra blank lines after headers
            if line.startswith('#'):
                # Skip the next blank line if it exists
                if (i + 1 < len(lines) and 
                    not lines[i + 1].strip() and 
                    i + 2 < len(lines) and 
                    lines[i + 2].strip()):
                    continue
        
        return '\n'.join(optimized_lines)
    
    def _optimize_references(self, content: str) -> str:
        """Mark references section for smaller font."""
        # Add a comment that the PDF generator can use
        content = content.replace(
            '# References',
            '# References\n<!-- PDF: Use smaller font for this section -->'
        )
        return content
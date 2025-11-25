"""Configuration management for references and bibliography."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CitationStyleConfig:
    """Configuration for citation and bibliography style."""
    type: str = "numeric"  # or "author-year"
    sort_order: str = "alphabetical"  # or "order_cited"
    include_doi: bool = True
    include_urls: bool = True
    max_authors: int = 10
    et_al_threshold: int = 10
    font_size: int = 9


@dataclass
class URLValidationConfig:
    """Configuration for URL validation."""
    prohibit_all_urls: bool = False
    allowed_domains: List[str] = field(default_factory=lambda: [".gov", ".edu", "nsf.gov", "doi.org"])
    unknown_domain_severity: str = "warning"


@dataclass
class ReferencesValidationConfig:
    """Configuration for references section validation."""
    allow_academic_urls: bool = True
    prohibit_cloud_storage: bool = True
    prohibited_domains: List[str] = field(default_factory=lambda: [
        "dropbox.com", "drive.google.com", "onedrive.com", 
        "facebook.com", "twitter.com", "linkedin.com"
    ])


@dataclass
class ValidationConfig:
    """Configuration for validation settings."""
    # Citation validation
    require_bib_entries: bool = True
    warn_unused_entries: bool = True
    check_syntax: bool = True
    allowed_sections: List[str] = field(default_factory=list)
    
    # URL validation
    main_document: URLValidationConfig = field(default_factory=URLValidationConfig)
    references: ReferencesValidationConfig = field(default_factory=ReferencesValidationConfig)
    
    # Email validation
    prohibit_emails_everywhere: bool = True
    prohibited_email_sections: List[str] = field(default_factory=lambda: [
        "project_description", "references", "biographical_sketch"
    ])


@dataclass
class PDFReferencesConfig:
    """Configuration for PDF generation of references."""
    separate_references: bool = True
    page_break_before: bool = True
    section_title: str = "References Cited"
    font_size: int = 9
    font_family: str = "inherit"
    line_spacing: float = 1.0
    hanging_indent: bool = True
    entry_spacing: str = "6pt"
    number_format: str = "[{number}]"


@dataclass
class ReferencesConfig:
    """Complete configuration for references and bibliography management."""
    # Bibliography settings
    default_filename: str = "references.bib"
    search_paths: List[str] = field(default_factory=lambda: [
        ".", "references/", "bibliography/", "docs/", "sections/"
    ])
    style: CitationStyleConfig = field(default_factory=CitationStyleConfig)
    
    # Validation settings
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    
    # PDF settings
    pdf: PDFReferencesConfig = field(default_factory=PDFReferencesConfig)
    
    # Output settings
    bibliography_markdown: str = "references.md"
    bibliography_json: str = "references.json"
    main_document_pdf: str = "proposal.pdf"
    references_pdf: str = "references.pdf"
    citation_report: str = "citation_report.md"
    url_validation_report: str = "url_validation_report.md"
    
    # Export settings
    export_used_only: bool = True
    include_statistics: bool = True
    auto_validate: bool = True

    @classmethod
    def from_yaml(cls, config_data: Dict[str, Any]) -> 'ReferencesConfig':
        """Create configuration from YAML data."""
        try:
            # Extract main sections
            bibliography = config_data.get('bibliography', {})
            validation = config_data.get('validation', {})
            pdf = config_data.get('pdf', {})
            output = config_data.get('output', {})
            
            # Build citation style config
            style_data = bibliography.get('style', {})
            style = CitationStyleConfig(
                type=style_data.get('type', 'numeric'),
                sort_order=style_data.get('sort_order', 'alphabetical'),
                include_doi=style_data.get('include_doi', True),
                include_urls=style_data.get('include_urls', True),
                max_authors=style_data.get('max_authors', 10),
                et_al_threshold=style_data.get('et_al_threshold', 10),
                font_size=style_data.get('font_size', 9)
            )
            
            # Build validation configs
            citations = validation.get('citations', {})
            urls = validation.get('urls', {})
            emails = validation.get('emails', {})
            
            main_doc_urls = URLValidationConfig(
                prohibit_all_urls=urls.get('main_document', {}).get('prohibit_all_urls', False),
                allowed_domains=urls.get('main_document', {}).get('allowed_domains', [".gov", ".edu", "nsf.gov", "doi.org"]),
                unknown_domain_severity=urls.get('main_document', {}).get('unknown_domain_severity', 'warning')
            )
            
            refs_urls = ReferencesValidationConfig(
                allow_academic_urls=urls.get('references', {}).get('allow_academic_urls', True),
                prohibit_cloud_storage=urls.get('references', {}).get('prohibit_cloud_storage', True),
                prohibited_domains=urls.get('references', {}).get('prohibited_domains', [
                    "dropbox.com", "drive.google.com", "onedrive.com", 
                    "facebook.com", "twitter.com", "linkedin.com"
                ])
            )
            
            validation_config = ValidationConfig(
                require_bib_entries=citations.get('require_bib_entries', True),
                warn_unused_entries=citations.get('warn_unused_entries', True),
                check_syntax=citations.get('check_syntax', True),
                allowed_sections=citations.get('allowed_sections', []),
                main_document=main_doc_urls,
                references=refs_urls,
                prohibit_emails_everywhere=emails.get('prohibit_everywhere', True),
                prohibited_email_sections=emails.get('prohibited_sections', [
                    "project_description", "references", "biographical_sketch"
                ])
            )
            
            # Build PDF config
            pdf_font = pdf.get('font', {})
            pdf_formatting = pdf.get('formatting', {})
            
            pdf_config = PDFReferencesConfig(
                separate_references=pdf.get('separate_references', True),
                page_break_before=pdf.get('page_break_before', True),
                section_title=pdf.get('section_title', 'References Cited'),
                font_size=pdf_font.get('size', 9),
                font_family=pdf_font.get('family', 'inherit'),
                line_spacing=pdf_font.get('line_spacing', 1.0),
                hanging_indent=pdf_formatting.get('hanging_indent', True),
                entry_spacing=pdf_formatting.get('entry_spacing', '6pt'),
                number_format=pdf_formatting.get('number_format', '[{number}]')
            )
            
            # Extract output settings
            filenames = output.get('filenames', {})
            export_settings = output.get('export', {})
            
            return cls(
                default_filename=bibliography.get('default_filename', 'references.bib'),
                search_paths=bibliography.get('search_paths', [
                    ".", "references/", "bibliography/", "docs/", "sections/"
                ]),
                style=style,
                validation=validation_config,
                pdf=pdf_config,
                bibliography_markdown=filenames.get('bibliography_markdown', 'references.md'),
                bibliography_json=filenames.get('bibliography_json', 'references.json'),
                main_document_pdf=filenames.get('main_document_pdf', 'proposal.pdf'),
                references_pdf=filenames.get('references_pdf', 'references.pdf'),
                citation_report=filenames.get('citation_report', 'citation_report.md'),
                url_validation_report=filenames.get('url_validation_report', 'url_validation_report.md'),
                export_used_only=export_settings.get('export_used_only', True),
                include_statistics=export_settings.get('include_statistics', True),
                auto_validate=export_settings.get('auto_validate', True)
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse references configuration: {e}")
            return cls()  # Return default configuration
    
    @classmethod
    def load_from_file(cls, config_path: Path) -> 'ReferencesConfig':
        """Load configuration from a YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            return cls.from_yaml(config_data)
        except Exception as e:
            logger.warning(f"Failed to load references configuration from {config_path}: {e}")
            return cls()  # Return default configuration
    
    @classmethod
    def load_default(cls) -> 'ReferencesConfig':
        """Load default configuration from package data."""
        package_config = Path(__file__).parent.parent / "data" / "references_config.yaml"
        if package_config.exists():
            return cls.load_from_file(package_config)
        else:
            logger.warning("Default references configuration not found, using built-in defaults")
            return cls()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            'bibliography': {
                'default_filename': self.default_filename,
                'search_paths': self.search_paths,
                'style': {
                    'type': self.style.type,
                    'sort_order': self.style.sort_order,
                    'include_doi': self.style.include_doi,
                    'include_urls': self.style.include_urls,
                    'max_authors': self.style.max_authors,
                    'et_al_threshold': self.style.et_al_threshold,
                    'font_size': self.style.font_size
                }
            },
            'validation': {
                'citations': {
                    'require_bib_entries': self.validation.require_bib_entries,
                    'warn_unused_entries': self.validation.warn_unused_entries,
                    'check_syntax': self.validation.check_syntax,
                    'allowed_sections': self.validation.allowed_sections
                },
                'urls': {
                    'main_document': {
                        'prohibit_all_urls': self.validation.main_document.prohibit_all_urls,
                        'allowed_domains': self.validation.main_document.allowed_domains,
                        'unknown_domain_severity': self.validation.main_document.unknown_domain_severity
                    },
                    'references': {
                        'allow_academic_urls': self.validation.references.allow_academic_urls,
                        'prohibit_cloud_storage': self.validation.references.prohibit_cloud_storage,
                        'prohibited_domains': self.validation.references.prohibited_domains
                    }
                },
                'emails': {
                    'prohibit_everywhere': self.validation.prohibit_emails_everywhere,
                    'prohibited_sections': self.validation.prohibited_email_sections
                }
            },
            'pdf': {
                'separate_references': self.pdf.separate_references,
                'page_break_before': self.pdf.page_break_before,
                'section_title': self.pdf.section_title,
                'font': {
                    'size': self.pdf.font_size,
                    'family': self.pdf.font_family,
                    'line_spacing': self.pdf.line_spacing
                },
                'formatting': {
                    'hanging_indent': self.pdf.hanging_indent,
                    'entry_spacing': self.pdf.entry_spacing,
                    'number_format': self.pdf.number_format
                }
            },
            'output': {
                'filenames': {
                    'bibliography_markdown': self.bibliography_markdown,
                    'bibliography_json': self.bibliography_json,
                    'main_document_pdf': self.main_document_pdf,
                    'references_pdf': self.references_pdf,
                    'citation_report': self.citation_report,
                    'url_validation_report': self.url_validation_report
                },
                'export': {
                    'export_used_only': self.export_used_only,
                    'include_statistics': self.include_statistics,
                    'auto_validate': self.auto_validate
                }
            }
        }
    
    def save_to_file(self, output_path: Path) -> None:
        """Save configuration to a YAML file."""
        config_dict = self.to_dict()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
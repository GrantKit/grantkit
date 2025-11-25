"""PDF generation configuration with NSF PAPPG 24-1 compliance."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from ..utils.nsf_rules import get_nsf_rules, validate_nsf_compliance
except ImportError:
    # Fallback for import issues
    def get_nsf_rules():
        return None

    def validate_nsf_compliance(config):
        return []


@dataclass
class PDFConfig:
    """Configuration for PDF generation."""

    # Engine selection
    engine: str = "pandoc"  # "pandoc" or "weasyprint"

    # Font settings - PAPPG 24-1 II.C.2.d.i.(a)
    font_size: int = 10  # NSF minimum 10pt - use minimum for maximum content
    font_family: str = "Times New Roman"  # NSF-compliant font

    # Spacing
    line_spacing: str = "single"  # "single" or "1.5"
    paragraph_spacing: float = 0.0  # Points between paragraphs
    section_spacing: float = 6.0  # Points between sections

    # Page layout
    margin_top: float = 1.0  # inches
    margin_bottom: float = 1.0  # inches
    margin_left: float = 1.0  # inches
    margin_right: float = 1.0  # inches

    # Content optimization
    optimize_space: bool = True
    hyphenation: bool = True
    widow_orphan_control: bool = True
    figure_compression: float = 0.9  # Scale factor for figures

    # References formatting - PAPPG 24-1 II.C.2.d.i.(a) allows smaller fonts for references
    reference_font_size: Optional[int] = (
        9  # Smaller font for references (NSF allows)
    )

    # PDF output settings
    pdf_quality: str = "high"  # "draft", "normal", "high"
    compress_images: bool = True
    embed_fonts: bool = True

    # Validation
    page_limit: Optional[int] = None
    warn_threshold: float = 0.9  # Warn when reaching 90% of page limit

    @classmethod
    def from_yaml(cls, config_dict: Dict[str, Any]) -> "PDFConfig":
        """Create PDFConfig from YAML configuration."""
        pdf_config = config_dict.get("pdf", {})

        # Filter only valid fields
        valid_fields = {
            field.name for field in cls.__dataclass_fields__.values()
        }
        filtered_config = {
            k: v for k, v in pdf_config.items() if k in valid_fields
        }

        return cls(**filtered_config)

    def to_pandoc_args(self) -> List[str]:
        """Convert config to pandoc command line arguments."""
        args = []

        # Basic PDF engine
        args.extend(["--pdf-engine", "xelatex"])  # Better Unicode support

        # Variables for LaTeX template
        args.extend(["-V", f"fontsize={self.font_size}pt"])
        args.extend(["-V", f"mainfont={self.font_family}"])
        args.extend(["-V", f"margin-top={self.margin_top}in"])
        args.extend(["-V", f"margin-bottom={self.margin_bottom}in"])
        args.extend(["-V", f"margin-left={self.margin_left}in"])
        args.extend(["-V", f"margin-right={self.margin_right}in"])

        if self.line_spacing == "single":
            args.extend(["-V", "linestretch=1.0"])
        elif self.line_spacing == "1.5":
            args.extend(["-V", "linestretch=1.5"])

        # Hyphenation
        if not self.hyphenation:
            args.extend(["-V", "hyphenation=false"])

        # Quality settings
        if self.pdf_quality == "high":
            args.extend(["-V", "graphics=true"])
        elif self.pdf_quality == "draft":
            args.append("--draft")

        return args

    def validate(self) -> List[str]:
        """Validate configuration against NSF PAPPG 24-1 requirements."""
        issues = []

        # Use NSF rules loader if available
        config_dict = {
            "font_size": self.font_size,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
        }

        nsf_issues = validate_nsf_compliance(config_dict)
        issues.extend(nsf_issues)

        # Additional validation
        if self.font_size > 12:
            issues.append(
                f"⚠️  Font size {self.font_size}pt is unusually large for NSF proposals"
            )

        # Line spacing validation - PAPPG 24-1 II.C.2.d.i.(b)
        if self.line_spacing not in ["single", "1.5"]:
            issues.append(
                f"⚠️  Line spacing '{self.line_spacing}' may not comply with NSF density requirements"
            )
            issues.append(
                "   NSF Rule: PAPPG 24-1 II.C.2.d.i.(b) allows no more than 6 lines per vertical inch"
            )

        return issues


@dataclass
class NSFProgramConfig:
    """NSF program-specific PDF requirements."""

    program_id: str
    page_limit: int
    allow_smaller_reference_font: bool = True
    require_single_spacing: bool = False
    max_file_size_mb: float = 10.0  # PDF file size limit

    @classmethod
    def get_program_configs() -> Dict[str, "NSFProgramConfig"]:
        """Get predefined NSF program configurations."""
        return {
            "pose-phase-2": NSFProgramConfig(
                program_id="pose-phase-2",
                page_limit=15,
                allow_smaller_reference_font=True,
                require_single_spacing=False,
                max_file_size_mb=10.0,
            ),
            "career": NSFProgramConfig(
                program_id="career",
                page_limit=15,
                allow_smaller_reference_font=True,
                require_single_spacing=False,
                max_file_size_mb=10.0,
            ),
            "cssi": NSFProgramConfig(
                program_id="cssi",
                page_limit=15,
                allow_smaller_reference_font=True,
                require_single_spacing=False,
                max_file_size_mb=10.0,
            ),
        }

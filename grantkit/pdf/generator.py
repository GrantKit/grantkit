"""Main PDF generator for NSF grant proposals."""

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..references import BibliographyGenerator, CitationExtractor
from .config import NSFProgramConfig, PDFConfig
from .optimizer import ContentOptimizer, OptimizationSuggestion
from .templates import LaTeXTemplateManager
from .validator import PDFValidationResult, PDFValidator

logger = logging.getLogger(__name__)


@dataclass
class PDFGenerationResult:
    """Result from PDF generation."""

    success: bool
    output_path: Optional[Path]
    page_count: int
    file_size_mb: float
    generation_time_seconds: float
    validation_result: Optional[PDFValidationResult]
    optimization_suggestions: List[OptimizationSuggestion]
    errors: List[str]
    warnings: List[str]
    log_path: Optional[Path] = None
    # New fields for separate references handling
    main_document_pages: Optional[int] = None
    references_pages: Optional[int] = None
    references_path: Optional[Path] = None
    citation_count: int = 0


class PDFGenerator:
    """Generates NSF-compliant PDFs from markdown content."""

    def __init__(
        self,
        config: Optional[PDFConfig] = None,
        project_root: Optional[Path] = None,
    ):
        self.config = config or PDFConfig()
        self.template_manager = LaTeXTemplateManager()
        self.optimizer = ContentOptimizer()
        self.validator = PDFValidator()

        # Initialize bibliography generator if project root provided
        if project_root:
            self.bibliography_generator = BibliographyGenerator(project_root)
            self.citation_extractor = CitationExtractor()
        else:
            self.bibliography_generator = None
            self.citation_extractor = None

        # Check for required tools
        self._check_dependencies()

    def generate_separated_pdfs(
        self,
        markdown_content: str,
        main_output_path: Path,
        references_output_path: Optional[Path] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        optimize: bool = True,
        validate: bool = True,
        program_config: Optional[NSFProgramConfig] = None,
    ) -> PDFGenerationResult:
        """Generate separate PDFs for main document and references.

        This method creates TWO separate PDFs:
        1. Main document without references (for page limit compliance)
        2. References document (doesn't count toward page limits)

        Args:
            markdown_content: The full proposal content with citations
            main_output_path: Path for main document PDF
            references_output_path: Path for references PDF (auto-generated if None)
            title: Document title
            author: Document author
            optimize: Whether to optimize content
            validate: Whether to validate results
            program_config: NSF program configuration

        Returns:
            PDFGenerationResult with both PDFs generated
        """
        import time

        start_time = time.time()

        errors = []
        warnings = []

        if not self.bibliography_generator:
            errors.append(
                "Bibliography generator not initialized - project root required"
            )
            return PDFGenerationResult(
                success=False,
                output_path=None,
                page_count=0,
                file_size_mb=0.0,
                generation_time_seconds=0.0,
                validation_result=None,
                optimization_suggestions=[],
                errors=errors,
                warnings=[],
            )

        try:
            # Set default references path
            if not references_output_path:
                references_output_path = main_output_path.with_name(
                    f"{main_output_path.stem}_references{main_output_path.suffix}"
                )

            # Process content to separate main from references
            main_content, used_citations = (
                self.bibliography_generator.process_content_with_citations(
                    markdown_content
                )
            )

            # Generate references document
            references_result = None
            if used_citations:
                bib_result = self.bibliography_generator.create_separate_references_document(
                    main_content
                )
                if bib_result.success:
                    references_content = bib_result.bibliography_content

                    # Generate references PDF
                    references_result = self.generate_pdf(
                        references_content,
                        references_output_path,
                        title=(
                            f"References Cited - {title}"
                            if title
                            else "References Cited"
                        ),
                        author=author,
                        optimize=False,  # Don't optimize references
                        validate=validate,
                        program_config=program_config,
                        separate_references=False,  # Already separated
                    )

                    if not references_result.success:
                        warnings.append("Failed to generate references PDF")
                        warnings.extend(references_result.warnings)

                else:
                    errors.extend(bib_result.errors)
                    warnings.extend(bib_result.warnings)

            # Generate main document PDF (without references)
            main_result = self.generate_pdf(
                main_content,
                main_output_path,
                title=title,
                author=author,
                optimize=optimize,
                validate=validate,
                program_config=program_config,
                separate_references=False,  # Already separated
            )

            if not main_result.success:
                errors.extend(main_result.errors)
                warnings.extend(main_result.warnings)

            generation_time = time.time() - start_time

            # Combine results
            total_success = main_result.success and (
                not references_result or references_result.success
            )

            return PDFGenerationResult(
                success=total_success,
                output_path=main_output_path if main_result.success else None,
                page_count=main_result.page_count,
                file_size_mb=main_result.file_size_mb,
                generation_time_seconds=generation_time,
                validation_result=main_result.validation_result,
                optimization_suggestions=main_result.optimization_suggestions,
                errors=errors + main_result.errors,
                warnings=warnings + main_result.warnings,
                log_path=main_result.log_path,
                main_document_pages=main_result.page_count,
                references_pages=(
                    references_result.page_count if references_result else 0
                ),
                references_path=(
                    references_output_path
                    if references_result and references_result.success
                    else None
                ),
                citation_count=len(used_citations),
            )

        except Exception as e:
            logger.exception("Separated PDF generation failed")
            generation_time = time.time() - start_time

            return PDFGenerationResult(
                success=False,
                output_path=None,
                page_count=0,
                file_size_mb=0.0,
                generation_time_seconds=generation_time,
                validation_result=None,
                optimization_suggestions=[],
                errors=[f"Separated PDF generation failed: {e}"],
                warnings=warnings,
            )

    def generate_pdf(
        self,
        markdown_content: str,
        output_path: Path,
        title: Optional[str] = None,
        author: Optional[str] = None,
        optimize: bool = True,
        validate: bool = True,
        program_config: Optional[NSFProgramConfig] = None,
        separate_references: bool = True,
    ) -> PDFGenerationResult:
        """Generate PDF from markdown content."""

        import time

        start_time = time.time()

        errors = []
        warnings = []
        optimization_suggestions = []

        try:
            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Apply optimizations if requested
                if optimize and self.config.optimize_space:
                    # Analyze content first
                    analysis = self.optimizer.analyze_content(markdown_content)
                    estimated_pages = analysis["estimated_pages"]

                    target_pages = (
                        program_config.page_limit
                        if program_config
                        else self.config.page_limit
                    )

                    if target_pages and estimated_pages > target_pages:
                        optimization_suggestions = (
                            self.optimizer.suggest_optimizations(
                                markdown_content, estimated_pages, target_pages
                            )
                        )

                        # Apply automatic optimizations (easy ones)
                        auto_optimizations = [
                            s.type
                            for s in optimization_suggestions
                            if s.priority <= 2
                            and s.implementation_difficulty == "easy"
                        ]

                        if auto_optimizations:
                            markdown_content = (
                                self.optimizer.apply_optimizations(
                                    markdown_content, auto_optimizations
                                )
                            )
                            warnings.append(
                                f"Applied automatic optimizations: {', '.join(auto_optimizations)}"
                            )

                # Handle references separation
                main_content = markdown_content
                references_content = ""
                citation_count = 0

                if separate_references and self.bibliography_generator:
                    # Extract citations and process content
                    main_content, used_citations = (
                        self.bibliography_generator.process_content_with_citations(
                            markdown_content
                        )
                    )
                    citation_count = len(used_citations)

                    if used_citations:
                        # Generate references section
                        bib_result = self.bibliography_generator.create_separate_references_document(
                            main_content
                        )
                        if bib_result.success:
                            references_content = (
                                bib_result.bibliography_content
                            )
                            warnings.extend(bib_result.warnings)
                        else:
                            errors.extend(bib_result.errors)
                            warnings.extend(bib_result.warnings)

                # Generate PDF using selected engine
                if self.config.engine == "pandoc":
                    result = self._generate_with_pandoc(
                        main_content,
                        references_content,
                        output_path,
                        temp_path,
                        title,
                        author,
                        program_config,
                        separate_references,
                    )
                elif self.config.engine == "weasyprint":
                    result = self._generate_with_weasyprint(
                        main_content,
                        references_content,
                        output_path,
                        temp_path,
                        title,
                        author,
                        program_config,
                        separate_references,
                    )
                else:
                    raise ValueError(
                        f"Unknown PDF engine: {self.config.engine}"
                    )

                if not result.success:
                    errors.extend(result.errors)
                    warnings.extend(result.warnings)

                # Validate the generated PDF
                validation_result = None
                if validate and result.success and result.output_path:
                    page_limit = (
                        program_config.page_limit
                        if program_config
                        else self.config.page_limit
                    )
                    validation_result = self.validator.validate_pdf(
                        result.output_path, page_limit
                    )

                    if not validation_result.is_valid:
                        warnings.append("Generated PDF failed validation")
                        for issue in validation_result.issues:
                            warnings.append(f"Validation issue: {issue}")

                generation_time = time.time() - start_time

                return PDFGenerationResult(
                    success=result.success,
                    output_path=result.output_path,
                    page_count=(
                        validation_result.page_count
                        if validation_result
                        else 0
                    ),
                    file_size_mb=(
                        validation_result.file_size_mb
                        if validation_result
                        else 0.0
                    ),
                    generation_time_seconds=generation_time,
                    validation_result=validation_result,
                    optimization_suggestions=optimization_suggestions,
                    errors=errors + result.errors,
                    warnings=warnings + result.warnings,
                    log_path=result.log_path,
                    main_document_pages=result.main_document_pages,
                    references_pages=result.references_pages,
                    references_path=result.references_path,
                    citation_count=citation_count,
                )

        except Exception as e:
            logger.exception("PDF generation failed")
            generation_time = time.time() - start_time

            return PDFGenerationResult(
                success=False,
                output_path=None,
                page_count=0,
                file_size_mb=0.0,
                generation_time_seconds=generation_time,
                validation_result=None,
                optimization_suggestions=optimization_suggestions,
                errors=[f"PDF generation failed: {e}"],
                warnings=warnings,
            )

    def _generate_with_pandoc(
        self,
        main_content: str,
        references_content: str,
        output_path: Path,
        temp_path: Path,
        title: Optional[str],
        author: Optional[str],
        program_config: Optional[NSFProgramConfig],
        separate_references: bool = True,
    ) -> "PDFGenerationResult":
        """Generate PDF using Pandoc."""

        try:
            # Prepare content - combine main and references if separate
            full_content = main_content
            if separate_references and references_content:
                # Add page break before references
                full_content += "\n\n\\newpage\n\n" + references_content

            # Prepare input file
            input_file = temp_path / "input.md"
            input_file.write_text(full_content, encoding="utf-8")

            # Create LaTeX template
            template_content = self.template_manager.get_nsf_template(
                optimize_space=self.config.optimize_space
            )
            template_file = temp_path / "template.latex"
            template_file.write_text(template_content, encoding="utf-8")

            # Prepare pandoc command
            cmd = [
                "pandoc",
                str(input_file),
                "-o",
                str(output_path),
                "--template",
                str(template_file),
                "--pdf-engine=xelatex",
                "-V",
                "geometry:margin=1in",
                "-V",
                f"fontsize={self.config.font_size}pt",
                "-V",
                f"mainfont={self.config.font_family}",
            ]

            # Add title and author if provided
            if title:
                cmd.extend(["-V", f"title={title}"])
            if author:
                cmd.extend(["-V", f"author={author}"])

            # Add additional pandoc arguments from config
            cmd.extend(self.config.to_pandoc_args())

            # Add reference font size if enabled
            if self.config.reference_font_size:
                cmd.extend(
                    [
                        "-V",
                        f"reference_font_size={self.config.reference_font_size}",
                    ]
                )

            # Run pandoc
            log_file = temp_path / "pandoc.log"
            with open(log_file, "w") as log:
                result = subprocess.run(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=temp_path,
                    timeout=300,  # 5 minute timeout
                )

            # Copy log file to permanent location for debugging
            if output_path.parent.is_dir():
                permanent_log = (
                    output_path.parent / f"{output_path.stem}_generation.log"
                )
                permanent_log.write_text(
                    log_file.read_text(), encoding="utf-8"
                )
                log_path = permanent_log
            else:
                log_path = None

            if result.returncode == 0 and output_path.exists():
                return PDFGenerationResult(
                    success=True,
                    output_path=output_path,
                    page_count=0,  # Will be filled by validation
                    file_size_mb=0.0,  # Will be filled by validation
                    generation_time_seconds=0.0,  # Will be filled by caller
                    validation_result=None,
                    optimization_suggestions=[],
                    errors=[],
                    warnings=[],
                    log_path=log_path,
                )
            else:
                log_content = (
                    log_file.read_text(encoding="utf-8")
                    if log_file.exists()
                    else ""
                )
                return PDFGenerationResult(
                    success=False,
                    output_path=None,
                    page_count=0,
                    file_size_mb=0.0,
                    generation_time_seconds=0.0,
                    validation_result=None,
                    optimization_suggestions=[],
                    errors=[
                        f"Pandoc failed with return code {result.returncode}",
                        log_content,
                    ],
                    warnings=[],
                    log_path=log_path,
                )

        except subprocess.TimeoutExpired:
            return PDFGenerationResult(
                success=False,
                output_path=None,
                page_count=0,
                file_size_mb=0.0,
                generation_time_seconds=0.0,
                validation_result=None,
                optimization_suggestions=[],
                errors=["PDF generation timed out after 5 minutes"],
                warnings=[],
            )
        except Exception as e:
            return PDFGenerationResult(
                success=False,
                output_path=None,
                page_count=0,
                file_size_mb=0.0,
                generation_time_seconds=0.0,
                validation_result=None,
                optimization_suggestions=[],
                errors=[f"Pandoc generation failed: {e}"],
                warnings=[],
            )

    def _generate_with_weasyprint(
        self,
        main_content: str,
        references_content: str,
        output_path: Path,
        temp_path: Path,
        title: Optional[str],
        author: Optional[str],
        program_config: Optional[NSFProgramConfig],
        separate_references: bool = True,
    ) -> "PDFGenerationResult":
        """Generate PDF using WeasyPrint as fallback."""

        try:
            import markdown
            import weasyprint

            # Prepare content - combine main and references if separate
            full_content = main_content
            if separate_references and references_content:
                # Add references section with clear break
                full_content += f"\n\n---\n\n{references_content}"

            # Convert markdown to HTML
            md = markdown.Markdown(
                extensions=[
                    "tables",
                    "codehilite",
                    "toc",
                    "fenced_code",
                    "attr_list",
                    "def_list",
                    "footnotes",
                ]
            )

            html_content = md.convert(full_content)

            # Create HTML document with NSF-compliant CSS
            css_content = self._get_nsf_css()

            full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title or 'NSF Proposal'}</title>
    <style>{css_content}</style>
</head>
<body>
    {f'<h1 class="title">{title}</h1>' if title else ''}
    {f'<p class="author">{author}</p>' if author else ''}
    {html_content}
</body>
</html>
"""

            # Write HTML to temporary file
            html_file = temp_path / "document.html"
            html_file.write_text(full_html, encoding="utf-8")

            # Generate PDF with WeasyPrint
            weasyprint.HTML(filename=str(html_file)).write_pdf(
                str(output_path)
            )

            if output_path.exists():
                return PDFGenerationResult(
                    success=True,
                    output_path=output_path,
                    page_count=0,
                    file_size_mb=0.0,
                    generation_time_seconds=0.0,
                    validation_result=None,
                    optimization_suggestions=[],
                    errors=[],
                    warnings=[
                        "Generated with WeasyPrint - may have different formatting than LaTeX"
                    ],
                )
            else:
                return PDFGenerationResult(
                    success=False,
                    output_path=None,
                    page_count=0,
                    file_size_mb=0.0,
                    generation_time_seconds=0.0,
                    validation_result=None,
                    optimization_suggestions=[],
                    errors=["WeasyPrint failed to generate PDF"],
                    warnings=[],
                )

        except ImportError as e:
            return PDFGenerationResult(
                success=False,
                output_path=None,
                page_count=0,
                file_size_mb=0.0,
                generation_time_seconds=0.0,
                validation_result=None,
                optimization_suggestions=[],
                errors=[f"WeasyPrint dependencies not available: {e}"],
                warnings=[],
            )
        except Exception as e:
            return PDFGenerationResult(
                success=False,
                output_path=None,
                page_count=0,
                file_size_mb=0.0,
                generation_time_seconds=0.0,
                validation_result=None,
                optimization_suggestions=[],
                errors=[f"WeasyPrint generation failed: {e}"],
                warnings=[],
            )

    def _get_nsf_css(self) -> str:
        """Get CSS for NSF-compliant formatting."""
        return f"""
@page {{
    size: letter;
    margin: 1in;
    @bottom-center {{
        content: counter(page);
        font-family: {self.config.font_family};
        font-size: 10pt;
    }}
}}

body {{
    font-family: {self.config.font_family};
    font-size: {self.config.font_size}pt;
    line-height: 1.2;
    margin: 0;
    padding: 0;
}}

.title {{
    font-size: {self.config.font_size + 2}pt;
    font-weight: bold;
    text-align: center;
    margin-bottom: 12pt;
}}

.author {{
    text-align: center;
    margin-bottom: 18pt;
}}

h1 {{
    font-size: {self.config.font_size + 1}pt;
    font-weight: bold;
    margin-top: 12pt;
    margin-bottom: 6pt;
}}

h2 {{
    font-size: {self.config.font_size}pt;
    font-weight: bold;
    margin-top: 10pt;
    margin-bottom: 4pt;
}}

h3 {{
    font-size: {self.config.font_size}pt;
    font-weight: bold;
    margin-top: 8pt;
    margin-bottom: 3pt;
}}

p {{
    margin-top: 0pt;
    margin-bottom: 6pt;
    text-align: justify;
}}

ul, ol {{
    margin-top: 3pt;
    margin-bottom: 6pt;
    padding-left: 24pt;
}}

li {{
    margin-bottom: 2pt;
}}

table {{
    border-collapse: collapse;
    margin: 6pt 0;
    width: 100%;
}}

td, th {{
    border: 1pt solid black;
    padding: 3pt;
    font-size: {self.config.font_size - 1}pt;
}}

img {{
    max-width: 100%;
    height: auto;
}}

/* Optimize space in references */
.references {{
    font-size: {self.config.reference_font_size or self.config.font_size - 1}pt;
    line-height: 1.1;
}}

/* Prevent widows and orphans */
p, li {{
    orphans: 2;
    widows: 2;
}}

h1, h2, h3 {{
    page-break-after: avoid;
}}
"""

    def _check_dependencies(self) -> Dict[str, bool]:
        """Check for required dependencies."""
        dependencies = {
            "pandoc": self._check_pandoc(),
            "xelatex": self._check_xelatex(),
            "weasyprint": self._check_weasyprint(),
            "pypdf": self._check_pypdf(),
        }

        # Log missing dependencies
        missing = [
            name for name, available in dependencies.items() if not available
        ]
        if missing:
            logger.warning(f"Missing dependencies: {', '.join(missing)}")

        return dependencies

    def _check_pandoc(self) -> bool:
        """Check if pandoc is available."""
        try:
            result = subprocess.run(
                ["pandoc", "--version"], capture_output=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _check_xelatex(self) -> bool:
        """Check if XeLaTeX is available."""
        try:
            result = subprocess.run(
                ["xelatex", "--version"], capture_output=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _check_weasyprint(self) -> bool:
        """Check if WeasyPrint is available."""
        import importlib.util

        return importlib.util.find_spec("weasyprint") is not None

    def _check_pypdf(self) -> bool:
        """Check if pypdf is available."""
        import importlib.util

        return (
            importlib.util.find_spec("pypdf") is not None
            or importlib.util.find_spec("PyPDF2") is not None
        )

    def get_capability_report(self) -> Dict[str, any]:
        """Get a report of PDF generation capabilities."""
        deps = self._check_dependencies()

        capabilities = {
            "can_generate_pdf": deps["pandoc"]
            and deps["xelatex"]
            or deps["weasyprint"],
            "preferred_engine": (
                "pandoc"
                if deps["pandoc"] and deps["xelatex"]
                else "weasyprint"
            ),
            "can_validate_pdf": deps["pypdf"],
            "can_count_pages": deps["pypdf"] or self._has_pdf_tools(),
            "dependencies": deps,
            "recommendations": [],
        }

        # Add recommendations
        if not deps["pandoc"]:
            capabilities["recommendations"].append(
                "Install pandoc for best PDF quality"
            )
        if not deps["xelatex"]:
            capabilities["recommendations"].append(
                "Install XeLaTeX (texlive) for pandoc PDF generation"
            )
        if not deps["weasyprint"]:
            capabilities["recommendations"].append(
                "Install WeasyPrint as a fallback PDF engine"
            )
        if not deps["pypdf"]:
            capabilities["recommendations"].append(
                "Install pypdf for PDF validation and page counting"
            )

        return capabilities

    def _has_pdf_tools(self) -> bool:
        """Check if system PDF tools are available."""
        tools = ["pdfinfo", "pdftk", "qpdf"]
        return any(self._check_command(tool) for tool in tools)

    def _check_command(self, command: str) -> bool:
        """Check if a command is available."""
        try:
            result = subprocess.run(
                [command, "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

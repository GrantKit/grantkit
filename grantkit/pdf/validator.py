"""PDF validation for NSF compliance."""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None

logger = logging.getLogger(__name__)


@dataclass
class PDFValidationResult:
    """Results from PDF validation."""

    is_valid: bool
    page_count: int
    file_size_mb: float
    issues: List[str]
    warnings: List[str]
    font_compliance: bool
    margin_compliance: bool
    metadata: Dict[str, str]


class PDFValidator:
    """Validates generated PDFs against NSF requirements."""

    def __init__(self):
        # NSF PAPPG 24-1 Requirements
        self.nsf_requirements = {
            "max_file_size_mb": 10.0,  # PAPPG 24-1 II.C.1
            "required_margins": 1.0,  # inches - PAPPG 24-1 II.C.2.d.i.(c)
            "allowed_fonts": [  # PAPPG 24-1 II.C.2.d.i.(a)
                "Times New Roman",
                "Times",
                "Helvetica",
                "Arial",
                "Computer Modern",
                "Latin Modern",
                "TeX Gyre Termes",
            ],
            "min_font_size": 10,  # points - PAPPG 24-1 II.C.2.d.i.(a)
            "max_font_size": 12,
            "max_lines_per_inch": 6.0,  # PAPPG 24-1 II.C.2.d.i.(b)
        }

    def validate_pdf(
        self,
        pdf_path: Path,
        page_limit: Optional[int] = None,
        program_requirements: Optional[Dict] = None,
    ) -> PDFValidationResult:
        """Validate a PDF against NSF requirements."""

        if not pdf_path.exists():
            return PDFValidationResult(
                is_valid=False,
                page_count=0,
                file_size_mb=0.0,
                issues=[f"PDF file not found: {pdf_path}"],
                warnings=[],
                font_compliance=False,
                margin_compliance=False,
                metadata={},
            )

        issues = []
        warnings = []

        # Get basic file info
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)

        # Count pages and extract metadata
        page_count = 0
        metadata = {}
        font_compliance = True

        if PdfReader:
            try:
                with open(pdf_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    page_count = len(pdf_reader.pages)

                    if pdf_reader.metadata:
                        metadata = {
                            "title": pdf_reader.metadata.get("/Title", ""),
                            "author": pdf_reader.metadata.get("/Author", ""),
                            "creator": pdf_reader.metadata.get("/Creator", ""),
                            "producer": pdf_reader.metadata.get(
                                "/Producer", ""
                            ),
                        }
            except Exception as e:
                logger.warning(f"Failed to read PDF metadata: {e}")
                issues.append(f"Could not read PDF properly: {e}")
        else:
            # Fallback: try to count pages using system tools
            page_count = self._count_pages_fallback(pdf_path)
            warnings.append(
                "pypdf not available - limited validation performed"
            )

        # Validate page count
        if page_limit and page_count > page_limit:
            issues.append(
                f"❌ Page count violation: {page_count} pages exceeds limit of {page_limit}"
            )
            issues.append(
                f"   NSF Rule: PAPPG 24-1 II.C.2.d.i requires ≤{page_limit} pages"
            )
            issues.append(
                "   See: https://www.nsf.gov/pubs/policydocs/pappguide/nsf24001/index.jsp"
            )
        elif page_limit and page_count > page_limit * 0.9:
            warnings.append(
                f"⚠️  Page count ({page_count}) approaching limit ({page_limit})"
            )

        # Validate file size
        max_size = program_requirements.get(
            "max_file_size_mb", self.nsf_requirements["max_file_size_mb"]
        )
        if file_size_mb > max_size:
            issues.append(
                f"❌ File size violation: {file_size_mb:.1f}MB exceeds limit of {max_size}MB"
            )
            issues.append(
                f"   NSF Rule: PAPPG 24-1 II.C.1 requires PDF files ≤{max_size}MB"
            )
            issues.append(
                "   See: https://www.nsf.gov/pubs/policydocs/pappguide/nsf24001/index.jsp"
            )
        elif file_size_mb > max_size * 0.8:
            warnings.append(
                f"⚠️  File size ({file_size_mb:.1f}MB) approaching limit ({max_size}MB)"
            )

        # Font and margin compliance (would require more sophisticated PDF parsing)
        margin_compliance = (
            True  # Assume compliant unless we can detect otherwise
        )

        # Determine overall validity
        is_valid = len(issues) == 0

        return PDFValidationResult(
            is_valid=is_valid,
            page_count=page_count,
            file_size_mb=file_size_mb,
            issues=issues,
            warnings=warnings,
            font_compliance=font_compliance,
            margin_compliance=margin_compliance,
            metadata=metadata,
        )

    def count_pages(self, pdf_path: Path) -> int:
        """Count pages in a PDF file."""
        if not pdf_path.exists():
            return 0

        if PdfReader:
            try:
                with open(pdf_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    return len(pdf_reader.pages)
            except Exception as e:
                logger.warning(f"Failed to count pages with pypdf: {e}")

        # Fallback to system tools
        return self._count_pages_fallback(pdf_path)

    def _count_pages_fallback(self, pdf_path: Path) -> int:
        """Fallback method to count PDF pages using system tools."""
        try:
            # Try pdfinfo (poppler-utils)
            result = subprocess.run(
                ["pdfinfo", str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("Pages:"):
                        return int(line.split(":")[1].strip())
        except (
            subprocess.SubprocessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            pass

        try:
            # Try pdftk
            result = subprocess.run(
                ["pdftk", str(pdf_path), "dump_data"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("NumberOfPages:"):
                        return int(line.split(":")[1].strip())
        except (
            subprocess.SubprocessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            pass

        try:
            # Try qpdf
            result = subprocess.run(
                ["qpdf", "--show-npages", str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (
            subprocess.SubprocessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            pass

        logger.warning(
            f"Could not count pages in {pdf_path} - no suitable tools found"
        )
        return 0

    def check_nsf_compliance(self, pdf_path: Path) -> Dict[str, bool]:
        """Check specific NSF compliance requirements."""
        compliance = {
            "file_exists": pdf_path.exists(),
            "readable": False,
            "has_text": False,
            "reasonable_size": False,
        }

        if not compliance["file_exists"]:
            return compliance

        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        compliance["reasonable_size"] = (
            0.1 <= file_size_mb <= 50.0
        )  # Reasonable bounds

        if PdfReader:
            try:
                with open(pdf_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    compliance["readable"] = True

                    # Check if PDF has extractable text
                    if pdf_reader.pages:
                        first_page_text = pdf_reader.pages[0].extract_text()
                        compliance["has_text"] = (
                            len(first_page_text.strip()) > 50
                        )

            except Exception as e:
                logger.warning(f"PDF compliance check failed: {e}")

        return compliance

    def get_pdf_info(self, pdf_path: Path) -> Dict[str, any]:
        """Get comprehensive PDF information."""
        info = {
            "exists": pdf_path.exists(),
            "size_mb": 0.0,
            "page_count": 0,
            "metadata": {},
            "compliance_issues": [],
        }

        if not info["exists"]:
            info["compliance_issues"].append("File does not exist")
            return info

        info["size_mb"] = pdf_path.stat().st_size / (1024 * 1024)
        info["page_count"] = self.count_pages(pdf_path)

        # Basic validation
        validation_result = self.validate_pdf(pdf_path)
        info["metadata"] = validation_result.metadata
        info["compliance_issues"] = (
            validation_result.issues + validation_result.warnings
        )

        return info

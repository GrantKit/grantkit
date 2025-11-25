"""NSF compliance validation functionality."""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import markdown
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a validation issue found in the proposal."""

    severity: str  # 'error', 'warning', 'info'
    category: str  # 'formatting', 'content', 'compliance', etc.
    message: str
    location: Optional[str] = None  # file, section, line number
    suggestion: Optional[str] = None
    rule: Optional[str] = None  # NSF rule reference


@dataclass
class ValidationResult:
    """Result of validation checks."""

    passed: bool
    issues: List[ValidationIssue]
    warnings_count: int = 0
    errors_count: int = 0

    def __post_init__(self) -> None:
        self.warnings_count = sum(
            1 for i in self.issues if i.severity == "warning"
        )
        self.errors_count = sum(
            1 for i in self.issues if i.severity == "error"
        )
        self.passed = self.errors_count == 0


class NSFValidator:
    """NSF-specific compliance validator for grant proposals."""

    # NSF PAPPG 24-1 prohibited elements - comprehensive list
    PROHIBITED_URLS = [
        # Cloud storage services (PAPPG 24-1 II.C.2.d.i)
        "dropbox.com",
        "drive.google.com",
        "onedrive.com",
        "icloud.com",
        "box.com",
        "mediafire.com",
        "mega.nz",
        "wetransfer.com",
        # Social media and personal sites
        "facebook.com",
        "twitter.com",
        "linkedin.com",
        "instagram.com",
        "youtube.com",
        "tiktok.com",
        "snapchat.com",
        # Personal hosting/blogs
        "wordpress.com",
        "blogger.com",
        "tumblr.com",
        "medium.com",
        "squarespace.com",
        "wix.com",
        "weebly.com",
        # File sharing
        "fileshare.com",
        "4shared.com",
        "rapidshare.com",
    ]

    # Allowed domains for NSF proposals (PAPPG 24-1 guidelines)
    ALLOWED_URL_DOMAINS = [
        # Government and funding agencies
        ".gov",
        "nsf.gov",
        "nih.gov",
        "nasa.gov",
        "energy.gov",
        "nist.gov",
        "census.gov",
        "bls.gov",
        "cdc.gov",
        "epa.gov",
        # Academic institutions
        ".edu",
        # Academic organizations and journals
        ".org",
        "doi.org",
        "orcid.org",
        "researchgate.net",
        # Major academic publishers
        "springer.com",
        "springerlink.com",
        "elsevier.com",
        "sciencedirect.com",
        "nature.com",
        "science.org",
        "aaas.org",
        "pnas.org",
        "ieee.org",
        "ieeexplore.ieee.org",
        "acm.org",
        "dl.acm.org",
        "wiley.com",
        "onlinelibrary.wiley.com",
        "tandfonline.com",
        "sage.com",
        "journals.sagepub.com",
        "aps.org",
        "aip.org",
        # Preprint servers
        "arxiv.org",
        "biorxiv.org",
        "medrxiv.org",
        "preprints.org",
        # Code repositories (allowed for software/data sharing)
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        # Data repositories
        "zenodo.org",
        "figshare.com",
        "dryad.org",
        "dataverse.org",
        # Standards organizations
        "iso.org",
        "nist.gov",
        "ansi.org",
    ]

    PROHIBITED_PATTERNS = [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email addresses
        r"https?://(?:"
        + "|".join(PROHIBITED_URLS)
        + r")",  # Cloud storage links
    ]

    # Font and formatting requirements - PAPPG 24-1 II.C.2.d.i
    MIN_FONT_SIZE = 10  # points - PAPPG 24-1 II.C.2.d.i.(a)
    REQUIRED_MARGINS = 1.0  # inches - PAPPG 24-1 II.C.2.d.i.(c)
    MAX_LINES_PER_INCH = 6.0  # PAPPG 24-1 II.C.2.d.i.(b)

    def __init__(self, program_config: Optional[Dict[str, Any]] = None):
        """Initialize validator with program-specific configuration."""
        self.program_config = program_config or {}
        self.issues: List[ValidationIssue] = []

    def validate_proposal(
        self,
        content: str,
        content_type: str = "markdown",
        check_formatting: bool = True,
        check_content: bool = True,
        check_compliance: bool = True,
    ) -> ValidationResult:
        """Run comprehensive validation on proposal content.

        Args:
            content: The proposal content to validate
            content_type: Type of content ('markdown', 'html', 'text')
            check_formatting: Whether to check formatting compliance
            check_content: Whether to check content requirements
            check_compliance: Whether to check NSF-specific compliance

        Returns:
            ValidationResult with all issues found
        """
        self.issues = []

        try:
            if check_compliance:
                self._check_prohibited_content(content)
                self._check_non_ascii_characters(content)

            if check_content:
                self._check_content_requirements(content)
                self._check_section_structure(content)

            if check_formatting:
                self._check_formatting_requirements(content, content_type)

            if content_type == "markdown":
                # Convert to HTML for additional checks
                html_content = markdown.markdown(content)
                self._check_html_compliance(html_content)

        except Exception as e:
            self.issues.append(
                ValidationIssue(
                    severity="error",
                    category="validation",
                    message=f"Validation failed: {str(e)}",
                    rule="VALIDATOR_ERROR",
                )
            )

        return ValidationResult(
            passed=not any(i.severity == "error" for i in self.issues),
            issues=self.issues.copy(),
        )

    def validate_separated_content(
        self,
        main_content: str,
        references_content: str,
        validate_main: bool = True,
        validate_references: bool = True,
    ) -> ValidationResult:
        """Validate main document and references separately for NSF compliance.

        Args:
            main_content: Main proposal content (should not contain URLs except allowed ones)
            references_content: References section content (URLs allowed here)
            validate_main: Whether to validate main content
            validate_references: Whether to validate references content

        Returns:
            ValidationResult combining both validations
        """
        self.issues = []

        try:
            if validate_main:
                # Main content validation - stricter URL checking
                self._check_main_document_compliance(main_content)

            if validate_references:
                # References validation - more permissive for URLs
                self._check_references_compliance(references_content)

        except Exception as e:
            self.issues.append(
                ValidationIssue(
                    severity="error",
                    category="validation",
                    message=f"Separated content validation failed: {str(e)}",
                    rule="VALIDATOR_ERROR",
                )
            )

        return ValidationResult(
            passed=not any(i.severity == "error" for i in self.issues),
            issues=self.issues.copy(),
        )

    def _check_main_document_compliance(self, content: str) -> None:
        """Check main document for NSF compliance with stricter URL rules."""
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Check for email addresses (completely prohibited in main document)
            email_matches = re.findall(self.PROHIBITED_PATTERNS[0], line)
            for email in email_matches:
                self.issues.append(
                    ValidationIssue(
                        severity="error",
                        category="compliance",
                        message=f"Email address in main document: {email}",
                        location=f"Line {line_num}",
                        suggestion="Remove all email addresses from main document. Use Cover Sheet for contact information.",
                        rule="PAPPG 24-1 II.C.2.d.i: Email addresses prohibited in Project Description",
                    )
                )

            # Check for URLs in main document - only essential ones allowed
            url_matches = re.findall(r'https?://[^\s<>"]+', line)
            for url in url_matches:
                url_status = self._classify_url(url)

                if url_status["prohibited"]:
                    self.issues.append(
                        ValidationIssue(
                            severity="error",
                            category="compliance",
                            message=f"Prohibited URL in main document: {url}",
                            location=f"Line {line_num}",
                            suggestion="Remove prohibited URLs from main document. Essential references should be cited and listed in References section.",
                            rule="PAPPG 24-1 II.C.2.d.i: Prohibited services not allowed in Project Description",
                        )
                    )
                elif not url_status["allowed"]:
                    self.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="compliance",
                            message=f"URL in main document may be inappropriate: {url}",
                            location=f"Line {line_num}",
                            suggestion="Consider moving URL to References section or removing if not essential.",
                            rule="PAPPG 24-1 II.C.2.d.i: URLs in main document should be minimal and essential",
                        )
                    )

    def _check_references_compliance(self, content: str) -> None:
        """Check references section compliance - more permissive for URLs."""
        if not content or "references" not in content.lower():
            return

        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Email addresses still prohibited even in references
            email_matches = re.findall(self.PROHIBITED_PATTERNS[0], line)
            for email in email_matches:
                self.issues.append(
                    ValidationIssue(
                        severity="error",
                        category="compliance",
                        message=f"Email address in references: {email}",
                        location=f"References, Line {line_num}",
                        suggestion="Remove email addresses from references. Use author names and institutional affiliations only.",
                        rule="PAPPG 24-1: Email addresses prohibited throughout proposal",
                    )
                )

            # Check URLs in references - still prohibit cloud storage but allow academic URLs
            url_matches = re.findall(r'https?://[^\s<>"]+', line)
            for url in url_matches:
                if any(
                    prohibited in url.lower()
                    for prohibited in self.PROHIBITED_URLS
                ):
                    service = self._identify_prohibited_service(url)
                    self.issues.append(
                        ValidationIssue(
                            severity="error",
                            category="compliance",
                            message=f"Prohibited URL in references: {url}",
                            location=f"References, Line {line_num}",
                            suggestion=f"Replace {service} link with DOI, stable institutional URL, or remove if not accessible to reviewers.",
                            rule="PAPPG 24-1 II.C.2.d.i: Even in references, use stable, accessible URLs",
                        )
                    )

    def _check_prohibited_content(self, content: str) -> None:
        """Check for NSF-prohibited content like emails and cloud storage links."""
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Check for email addresses in project description
            email_matches = re.findall(self.PROHIBITED_PATTERNS[0], line)
            for email in email_matches:
                self.issues.append(
                    ValidationIssue(
                        severity="error",
                        category="compliance",
                        message=f"Email address found in project description: {email}",
                        location=f"Line {line_num}",
                        suggestion="Remove ALL email addresses from project description. Contact information belongs in Cover Sheet only.",
                        rule='PAPPG 24-1 II.C.2.d.i: "The Project Description must not include...email addresses of the PI(s), co-PI(s), or other senior/key personnel."',
                    )
                )

            # Check for prohibited cloud storage URLs
            for url_pattern in self.PROHIBITED_PATTERNS[1:]:
                url_matches = re.findall(url_pattern, line, re.IGNORECASE)
                for url in url_matches:
                    # Identify the specific service
                    service_name = self._identify_prohibited_service(url)
                    self.issues.append(
                        ValidationIssue(
                            severity="error",
                            category="compliance",
                            message=f"Prohibited cloud storage URL detected: {url}",
                            location=f"Line {line_num}",
                            suggestion=f"Replace {service_name} links with institutional repositories (e.g., university data repository, Zenodo, Figshare) or remove entirely.",
                            rule="PAPPG 24-1 II.C.2.d.i: Cloud storage and file-sharing services are prohibited. Use institutional repositories for data/software sharing.",
                        )
                    )

            # Check for other URLs and validate they're allowed
            all_url_matches = re.findall(r'https?://[^\s<>"]+', line)
            for url in all_url_matches:
                url_status = self._classify_url(url)

                if url_status["prohibited"]:
                    self.issues.append(
                        ValidationIssue(
                            severity="error",
                            category="compliance",
                            message=f"Prohibited URL type detected: {url}",
                            location=f"Line {line_num}",
                            suggestion=url_status["suggestion"],
                            rule=url_status["rule"],
                        )
                    )
                elif not url_status["allowed"]:
                    self.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="compliance",
                            message=f"Potentially inappropriate URL - verify necessity: {url}",
                            location=f"Line {line_num}",
                            suggestion="Ensure this URL is essential for reviewers. Consider if content can be summarized instead.",
                            rule="PAPPG 24-1 II.C.2.d.i: URLs should only link to essential resources for proposal evaluation.",
                        )
                    )

    def _check_non_ascii_characters(self, content: str) -> None:
        """Check for non-ASCII characters that might cause issues."""
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            for char_pos, char in enumerate(line):
                if ord(char) > 127:  # Non-ASCII character
                    char_name = unicodedata.name(char, f"U+{ord(char):04X}")
                    self.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="formatting",
                            message=f"Non-ASCII character '{char}' ({char_name}) found",
                            location=f"Line {line_num}, position {char_pos + 1}",
                            suggestion="Replace with ASCII equivalent to avoid encoding issues",
                            rule="PAPPG formatting guidelines",
                        )
                    )

    def _check_content_requirements(self, content: str) -> None:
        """Check content-specific requirements."""
        word_count = len(content.split())

        # Check minimum content length
        if word_count < 100:
            self.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message=f"Content appears very short: {word_count} words",
                    suggestion="Ensure adequate detail is provided for review",
                )
            )

        # Check for common required elements
        required_elements = [
            ("intellectual merit", r"intellectual\s+merit"),
            ("broader impacts", r"broader\s+impacts?"),
        ]

        content_lower = content.lower()
        for element_name, pattern in required_elements:
            if not re.search(pattern, content_lower):
                self.issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="content",
                        message=f"'{element_name}' section not clearly identified",
                        suggestion=f"Ensure {element_name} is explicitly addressed",
                        rule="PAPPG II.C.2.d.i",
                    )
                )

    def _check_section_structure(self, content: str) -> None:
        """Check document structure and organization."""
        # Extract headings
        headings = re.findall(r"^#{1,6}\s+(.+)$", content, re.MULTILINE)

        if not headings:
            self.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message="No section headings found",
                    suggestion="Use clear section headings to organize content",
                )
            )
            return

        # Check heading hierarchy
        heading_levels = []
        for heading_line in re.findall(
            r"^(#{1,6})\s+(.+)$", content, re.MULTILINE
        ):
            level = len(heading_line[0])
            heading_levels.append(level)

        # Check for skipped heading levels
        for i in range(1, len(heading_levels)):
            if heading_levels[i] > heading_levels[i - 1] + 1:
                self.issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="formatting",
                        message="Heading level skipped - may affect document structure",
                        location=f"Heading {i+1}",
                        suggestion="Use consecutive heading levels (e.g., # then ##, not # then ###)",
                    )
                )
                break

    def _check_formatting_requirements(
        self, content: str, content_type: str
    ) -> None:
        """Check formatting compliance requirements."""
        if content_type == "markdown":
            # Check for excessive emphasis
            bold_matches = len(re.findall(r"\*\*[^*]+\*\*|__[^_]+__", content))
            italic_matches = len(re.findall(r"\*[^*]+\*|_[^_]+_", content))

            total_emphasis = bold_matches + italic_matches
            word_count = len(content.split())

            if (
                word_count > 0 and total_emphasis / word_count > 0.05
            ):  # >5% of words emphasized
                self.issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="formatting",
                        message="Excessive use of emphasis (bold/italic)",
                        suggestion="Use emphasis sparingly for maximum impact",
                    )
                )

        # Check line length (for readability)
        lines = content.split("\n")
        long_lines = [i for i, line in enumerate(lines, 1) if len(line) > 120]

        if len(long_lines) > len(lines) * 0.1:  # >10% of lines are very long
            self.issues.append(
                ValidationIssue(
                    severity="info",
                    category="formatting",
                    message="Many lines are very long",
                    suggestion="Consider breaking long lines for better readability",
                )
            )

    def _check_html_compliance(self, html_content: str) -> None:
        """Check HTML output for compliance issues."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Check for potentially problematic elements
            problematic_tags = soup.find_all(
                ["script", "style", "iframe", "embed", "object"]
            )
            if problematic_tags:
                self.issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="compliance",
                        message="HTML contains potentially problematic elements",
                        suggestion="Review and remove script, style, iframe, or embed tags",
                    )
                )

            # Check table structure
            tables = soup.find_all("table")
            for i, table in enumerate(tables):
                if not table.find("th"):  # No header row
                    self.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="formatting",
                            message=f"Table {i+1} lacks header row",
                            suggestion="Add header row to tables for accessibility",
                        )
                    )

        except Exception as e:
            logger.warning(f"HTML compliance check failed: {e}")

    def _identify_prohibited_service(self, url: str) -> str:
        """Identify which prohibited service a URL belongs to."""
        url_lower = url.lower()
        service_names = {
            "dropbox.com": "Dropbox",
            "drive.google.com": "Google Drive",
            "onedrive.com": "OneDrive",
            "icloud.com": "iCloud",
            "box.com": "Box",
            "facebook.com": "Facebook",
            "twitter.com": "Twitter",
            "linkedin.com": "LinkedIn",
            "youtube.com": "YouTube",
            "wordpress.com": "WordPress",
            "blogger.com": "Blogger",
            "medium.com": "Medium",
        }

        for domain, name in service_names.items():
            if domain in url_lower:
                return name

        return "Unknown prohibited service"

    def _classify_url(self, url: str) -> dict:
        """Classify a URL as allowed, prohibited, or questionable."""
        url_lower = url.lower()

        # Check if explicitly prohibited
        for prohibited_domain in self.PROHIBITED_URLS:
            if prohibited_domain in url_lower:
                service = self._identify_prohibited_service(url)
                return {
                    "allowed": False,
                    "prohibited": True,
                    "suggestion": f"Remove {service} link. Use institutional repositories for data/software sharing.",
                    "rule": "PAPPG 24-1 II.C.2.d.i: Cloud storage and file-sharing services are prohibited.",
                }

        # Check if explicitly allowed
        for allowed_domain in self.ALLOWED_URL_DOMAINS:
            if allowed_domain in url_lower:
                return {
                    "allowed": True,
                    "prohibited": False,
                    "suggestion": "",
                    "rule": "",
                }

        # Check for common problematic patterns
        problematic_patterns = {
            r"personal\.": "Personal websites are discouraged",
            r"~[a-zA-Z]": "Personal user directories are discouraged",
            r"\.blogspot\.": "Blog platforms are discouraged",
            r"sites\.google\.com": "Personal Google Sites may be inappropriate",
        }

        for pattern, message in problematic_patterns.items():
            if re.search(pattern, url_lower):
                return {
                    "allowed": False,
                    "prohibited": True,
                    "suggestion": f"{message}. Use institutional or professional websites.",
                    "rule": "PAPPG 24-1 II.C.2.d.i: URLs should link to professional, stable resources.",
                }

        # Unknown domain - potentially questionable
        return {
            "allowed": False,
            "prohibited": False,
            "suggestion": "Verify this URL is appropriate and stable for reviewers.",
            "rule": "PAPPG 24-1 II.C.2.d.i",
        }

    def _is_allowed_url(self, url: str) -> bool:
        """Check if a URL is generally allowed in NSF proposals."""
        classification = self._classify_url(url)
        return classification["allowed"]

    def validate_biographical_sketch(self, content: str) -> ValidationResult:
        """Validate biographical sketch format and content."""
        self.issues = []

        # Check for required sections in biosketch
        required_sections = [
            "professional preparation",
            "appointments",
            "publications",
            "synergistic activities",
            "collaborators",
        ]

        content_lower = content.lower()
        for section in required_sections:
            if section not in content_lower:
                self.issues.append(
                    ValidationIssue(
                        severity="error",
                        category="content",
                        message=f"Required biosketch section missing: {section}",
                        rule="PAPPG II.C.2.f.i",
                    )
                )

        # Check page limit (biosketches are typically 2-3 pages)
        word_count = len(content.split())
        if word_count > 1500:  # Rough estimate for 3 pages
            self.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="formatting",
                    message="Biographical sketch may exceed page limit",
                    suggestion="Review length - typical limit is 2-3 pages",
                )
            )

        return ValidationResult(
            passed=not any(i.severity == "error" for i in self.issues),
            issues=self.issues.copy(),
        )

    def validate_budget_narrative(self, content: str) -> ValidationResult:
        """Validate budget narrative and justification."""
        self.issues = []

        # Check for required budget categories
        nsf_categories = [
            "senior personnel",
            "other personnel",
            "fringe benefits",
            "equipment",
            "travel",
            "participant support",
            "other direct costs",
        ]

        content_lower = content.lower()
        missing_categories = []

        for category in nsf_categories:
            if (
                category not in content_lower
                and category.replace(" ", "") not in content_lower
            ):
                missing_categories.append(category)

        if missing_categories:
            self.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message=f"Budget categories not mentioned: {', '.join(missing_categories)}",
                    suggestion="Ensure all relevant budget categories are justified",
                )
            )

        # Check for dollar amounts and justifications
        dollar_amounts = re.findall(r"\$[\d,]+", content)
        if not dollar_amounts:
            self.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message="No dollar amounts found in budget narrative",
                    suggestion="Include specific costs with justifications",
                )
            )

        return ValidationResult(
            passed=not any(i.severity == "error" for i in self.issues),
            issues=self.issues.copy(),
        )

    def get_validation_report(self, results: List[ValidationResult]) -> str:
        """Generate a comprehensive validation report."""
        report_lines = []
        report_lines.append("# NSF Proposal Validation Report")
        report_lines.append(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        total_errors = sum(r.errors_count for r in results)
        total_warnings = sum(r.warnings_count for r in results)

        if total_errors == 0 and total_warnings == 0:
            report_lines.append("✅ **All validation checks passed!**\n")
        else:
            report_lines.append(
                f"**Summary:** {total_errors} errors, {total_warnings} warnings\n"
            )

        for i, result in enumerate(results):
            if result.issues:
                report_lines.append(f"## Validation Set {i+1}")

                # Group issues by category
                by_category: Dict[str, List[ValidationIssue]] = {}
                for issue in result.issues:
                    if issue.category not in by_category:
                        by_category[issue.category] = []
                    by_category[issue.category].append(issue)

                for category, issues in by_category.items():
                    report_lines.append(f"\n### {category.title()} Issues")

                    for issue in issues:
                        icon = (
                            "❌"
                            if issue.severity == "error"
                            else "⚠️" if issue.severity == "warning" else "ℹ️"
                        )
                        report_lines.append(f"\n{icon} **{issue.message}**")

                        if issue.location:
                            report_lines.append(
                                f"   Location: {issue.location}"
                            )

                        if issue.suggestion:
                            report_lines.append(
                                f"   Suggestion: {issue.suggestion}"
                            )

                        if issue.rule:
                            report_lines.append(f"   Rule: {issue.rule}")

                report_lines.append("\n---\n")

        return "\n".join(report_lines)

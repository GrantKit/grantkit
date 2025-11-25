"""Tests for NSF compliance validation functionality."""

import pytest

from grantkit.core.validator import (
    NSFValidator,
    ValidationIssue,
    ValidationResult,
)


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_basic_issue(self):
        """Should create basic validation issue."""
        issue = ValidationIssue(
            severity="error",
            category="compliance",
            message="Test issue",
        )
        assert issue.severity == "error"
        assert issue.category == "compliance"
        assert issue.message == "Test issue"

    def test_issue_with_details(self):
        """Should store all details."""
        issue = ValidationIssue(
            severity="warning",
            category="formatting",
            message="Test warning",
            location="Line 42",
            suggestion="Fix it",
            rule="PAPPG II.C",
        )
        assert issue.location == "Line 42"
        assert issue.suggestion == "Fix it"
        assert issue.rule == "PAPPG II.C"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_passed_with_no_errors(self):
        """Should pass when no errors."""
        result = ValidationResult(passed=True, issues=[])
        assert result.passed is True
        assert result.errors_count == 0

    def test_failed_with_errors(self):
        """Should count errors correctly."""
        issues = [
            ValidationIssue("error", "compliance", "Error 1"),
            ValidationIssue("warning", "formatting", "Warning 1"),
            ValidationIssue("error", "content", "Error 2"),
        ]
        result = ValidationResult(passed=False, issues=issues)
        assert result.errors_count == 2
        assert result.warnings_count == 1
        assert result.passed is False


class TestNSFValidator:
    """Tests for NSFValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return NSFValidator()

    def test_clean_content_passes(self, validator):
        """Should pass clean content."""
        content = """
        # Project Description

        This project will develop new infrastructure.

        ## Intellectual Merit

        The intellectual merit is significant.

        ## Broader Impacts

        The broader impacts include education.
        """
        result = validator.validate_proposal(content)
        assert result.errors_count == 0

    def test_detects_email_address(self, validator):
        """Should detect email addresses."""
        content = "Contact: test@example.com for more info."
        result = validator.validate_proposal(content)

        email_issues = [
            i for i in result.issues if "email" in i.message.lower()
        ]
        assert len(email_issues) > 0

    def test_detects_dropbox_link(self, validator):
        """Should detect Dropbox links."""
        content = "See data at https://dropbox.com/s/abc123"
        result = validator.validate_proposal(content)

        dropbox_issues = [
            i for i in result.issues if "dropbox" in i.message.lower()
        ]
        assert len(dropbox_issues) > 0

    def test_detects_google_drive_link(self, validator):
        """Should detect Google Drive links."""
        content = "Files at https://drive.google.com/file/d/xyz"
        result = validator.validate_proposal(content)

        drive_issues = [
            i
            for i in result.issues
            if "google drive" in i.message.lower()
            or "prohibited" in i.message.lower()
        ]
        assert len(drive_issues) > 0

    def test_allows_github_link(self, validator):
        """Should allow GitHub links."""
        content = "Code at https://github.com/project/repo"
        result = validator.validate_proposal(content)

        # Should not have errors for GitHub
        github_errors = [
            i
            for i in result.issues
            if i.severity == "error" and "github" in i.message.lower()
        ]
        assert len(github_errors) == 0

    def test_allows_doi_link(self, validator):
        """Should allow DOI links."""
        content = "Reference: https://doi.org/10.1234/example"
        result = validator.validate_proposal(content)

        doi_errors = [
            i
            for i in result.issues
            if i.severity == "error" and "doi" in i.message.lower()
        ]
        assert len(doi_errors) == 0

    def test_allows_gov_links(self, validator):
        """Should allow .gov links."""
        content = "Data from https://census.gov/data"
        result = validator.validate_proposal(content)

        gov_errors = [
            i
            for i in result.issues
            if i.severity == "error" and "census.gov" in i.message.lower()
        ]
        assert len(gov_errors) == 0

    def test_warns_on_missing_intellectual_merit(self, validator):
        """Should warn if intellectual merit not found."""
        content = "# Project\n\nThis is the project description."
        result = validator.validate_proposal(content)

        merit_warnings = [
            i
            for i in result.issues
            if "intellectual merit" in i.message.lower()
        ]
        assert len(merit_warnings) > 0

    def test_warns_on_missing_broader_impacts(self, validator):
        """Should warn if broader impacts not found."""
        content = "# Project\n\nThis is the project description."
        result = validator.validate_proposal(content)

        impacts_warnings = [
            i for i in result.issues if "broader impacts" in i.message.lower()
        ]
        assert len(impacts_warnings) > 0

    def test_detects_non_ascii_characters(self, validator):
        """Should detect non-ASCII characters."""
        content = "This has smart quotes \u201chere\u201d"
        result = validator.validate_proposal(content)

        non_ascii = [
            i for i in result.issues if "non-ascii" in i.message.lower()
        ]
        assert len(non_ascii) > 0

    def test_warns_on_no_headings(self, validator):
        """Should warn if no section headings."""
        content = "Just plain text without any headings or structure."
        result = validator.validate_proposal(content)

        heading_warnings = [
            i for i in result.issues if "heading" in i.message.lower()
        ]
        assert len(heading_warnings) > 0


class TestBiographicalSketchValidation:
    """Tests for biographical sketch validation."""

    @pytest.fixture
    def validator(self):
        return NSFValidator()

    def test_complete_biosketch_passes(self, validator):
        """Should pass complete biosketch."""
        content = """
        # Biographical Sketch

        ## Professional Preparation
        PhD in Computer Science

        ## Appointments
        Professor, University

        ## Publications
        1. Paper one
        2. Paper two

        ## Synergistic Activities
        Service work

        ## Collaborators
        None to report
        """
        result = validator.validate_biographical_sketch(content)
        assert result.errors_count == 0

    def test_missing_section_fails(self, validator):
        """Should fail if required section missing."""
        content = """
        # Biographical Sketch

        ## Professional Preparation
        PhD in Computer Science

        ## Publications
        Papers here
        """
        result = validator.validate_biographical_sketch(content)
        assert result.errors_count > 0


class TestBudgetNarrativeValidation:
    """Tests for budget narrative validation."""

    @pytest.fixture
    def validator(self):
        return NSFValidator()

    def test_complete_budget_passes(self, validator):
        """Should pass budget with all categories."""
        content = """
        # Budget Narrative

        ## Senior Personnel
        PI: $50,000

        ## Other Personnel
        Graduate student: $30,000

        ## Fringe Benefits
        32% of salaries

        ## Equipment
        Server: $10,000

        ## Travel
        Conference: $2,000

        ## Participant Support
        None requested

        ## Other Direct Costs
        Publication fees: $1,000
        """
        result = validator.validate_budget_narrative(content)
        assert result.errors_count == 0

    def test_warns_on_missing_dollar_amounts(self, validator):
        """Should warn if no dollar amounts found."""
        content = """
        # Budget Narrative

        ## Senior Personnel
        PI salary for three months
        """
        result = validator.validate_budget_narrative(content)

        dollar_warnings = [
            i for i in result.issues if "dollar" in i.message.lower()
        ]
        assert len(dollar_warnings) > 0


class TestValidationReport:
    """Tests for validation report generation."""

    def test_generates_report(self):
        """Should generate readable report."""
        validator = NSFValidator()
        results = [
            ValidationResult(
                passed=True,
                issues=[
                    ValidationIssue("warning", "formatting", "Test warning")
                ],
            )
        ]

        report = validator.get_validation_report(results)

        assert "Validation Report" in report
        assert "Test warning" in report

    def test_empty_report_shows_success(self):
        """Should show success for no issues."""
        validator = NSFValidator()
        results = [ValidationResult(passed=True, issues=[])]

        report = validator.get_validation_report(results)

        assert "passed" in report.lower()

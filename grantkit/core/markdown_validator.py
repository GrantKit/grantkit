"""Markdown content validator for plain-text grants.

This module validates that response files don't contain markdown syntax
when the grant requires plain text (accepts_markdown: false in grant.yaml).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class MarkdownViolation:
    """Represents markdown syntax found in a plain-text grant file."""

    message: str
    file_path: str
    line_number: int
    line_content: str
    syntax_type: str  # 'table', 'header', 'bold', 'italic', 'link', 'code', 'list', 'comment'


@dataclass
class MarkdownValidationResult:
    """Result of markdown content validation."""

    passed: bool
    violations: List[MarkdownViolation] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.violations)


class MarkdownContentValidator:
    """Validates that content doesn't contain markdown syntax for plain-text grants."""

    # Patterns for detecting markdown syntax
    MARKDOWN_PATTERNS = [
        # Tables - pipe at start/end of line with content
        (r"^\s*\|.*\|", "table", "Markdown table syntax"),
        # Table separator rows
        (r"^\s*[\|\-\:\s]+\s*$", "table", "Markdown table separator"),
        # Headers - # at start of line
        (r"^#{1,6}\s+", "header", "Markdown header"),
        # Bold text - **text** or __text__
        (r"\*\*[^*]+\*\*", "bold", "Markdown bold text"),
        (r"__[^_]+__", "bold", "Markdown bold text"),
        # Italic text - *text* or _text_ (but not in URLs or normal underscores)
        (r"(?<!\*)\*[^*\s][^*]*[^*\s]\*(?!\*)", "italic", "Markdown italic/emphasis"),
        # Links - [text](url)
        (r"\[[^\]]+\]\([^)]+\)", "link", "Markdown link syntax"),
        # Code blocks - ```
        (r"^```", "code", "Markdown code block"),
        # Inline code - `code`
        (r"`[^`]+`", "code", "Markdown inline code"),
        # HTML comments - <!-- -->
        (r"<!--[\s\S]*?-->", "comment", "HTML comment"),
        # Bullet lists - lines starting with - or *
        (r"^\s*[-*]\s+\S", "list", "Markdown bullet list"),
        # Numbered lists - lines starting with 1. 2. etc
        (r"^\s*\d+\.\s+\S", "list", "Markdown numbered list"),
        # Blockquotes - > at start of line
        (r"^\s*>\s+", "blockquote", "Markdown blockquote"),
        # Horizontal rules - --- or ***
        (r"^[\-\*]{3,}\s*$", "rule", "Markdown horizontal rule"),
    ]

    def __init__(self, accepts_markdown: bool = True):
        """Initialize validator.

        Args:
            accepts_markdown: If True, markdown is allowed and validation passes.
                            If False, any markdown syntax is flagged.
        """
        self.accepts_markdown = accepts_markdown

    @classmethod
    def from_grant_yaml(cls, grant_yaml_path: Path) -> "MarkdownContentValidator":
        """Create validator from grant.yaml configuration.

        Args:
            grant_yaml_path: Path to grant.yaml file

        Returns:
            MarkdownContentValidator configured based on grant settings
        """
        if not grant_yaml_path.exists():
            # Default to accepting markdown
            return cls(accepts_markdown=True)

        with open(grant_yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # Check for accepts_markdown in full_application
        full_app = config.get("full_application", {})
        accepts_markdown = full_app.get("accepts_markdown", True)

        return cls(accepts_markdown=accepts_markdown)

    def validate_content(
        self, content: str, file_path: str = "content"
    ) -> MarkdownValidationResult:
        """Validate content for markdown syntax.

        Args:
            content: The text content to validate
            file_path: Name/path of file for error reporting

        Returns:
            MarkdownValidationResult with any violations found
        """
        # If markdown is accepted, no validation needed
        if self.accepts_markdown:
            return MarkdownValidationResult(passed=True, violations=[])

        violations = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            for pattern, syntax_type, message in self.MARKDOWN_PATTERNS:
                if re.search(pattern, line, re.MULTILINE):
                    violations.append(
                        MarkdownViolation(
                            message=message,
                            file_path=file_path,
                            line_number=line_num,
                            line_content=line[:100],  # Truncate long lines
                            syntax_type=syntax_type,
                        )
                    )
                    # Only report first violation per line to avoid duplicates
                    break

        return MarkdownValidationResult(
            passed=len(violations) == 0, violations=violations
        )

    def validate_directory(self, directory: Path) -> MarkdownValidationResult:
        """Validate all markdown files in a directory.

        Args:
            directory: Path to directory containing response files

        Returns:
            MarkdownValidationResult combining all file validations
        """
        all_violations = []

        if not directory.exists():
            return MarkdownValidationResult(passed=True, violations=[])

        for md_file in sorted(directory.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            result = self.validate_content(content, str(md_file.name))
            all_violations.extend(result.violations)

        return MarkdownValidationResult(
            passed=len(all_violations) == 0, violations=all_violations
        )

    def validate_grant_directory(self, grant_root: Path) -> MarkdownValidationResult:
        """Validate a grant directory using its grant.yaml configuration.

        Args:
            grant_root: Path to grant root directory (containing grant.yaml and responses/)

        Returns:
            MarkdownValidationResult for all response files
        """
        grant_yaml = grant_root / "grant.yaml"

        # Re-initialize from grant.yaml if it exists
        if grant_yaml.exists():
            validator = self.from_grant_yaml(grant_yaml)
        else:
            validator = self

        responses_dir = grant_root / "responses"
        return validator.validate_directory(responses_dir)

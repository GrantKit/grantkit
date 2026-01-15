"""Tests for markdown content validator."""

import pytest
from pathlib import Path
import tempfile
import yaml

from grantkit.core.markdown_validator import (
    MarkdownContentValidator,
    MarkdownViolation,
    MarkdownValidationResult,
)


class TestMarkdownContentValidator:
    """Tests for MarkdownContentValidator."""

    def test_detects_markdown_tables(self):
        """Tables should be detected in plain-text grants."""
        content = """This is some text.

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |

More text here."""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("table" in v.message.lower() for v in result.violations)

    def test_detects_markdown_headers(self):
        """Headers should be detected in plain-text grants."""
        content = """## This is a header

Some content here.

### Another header

More content."""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("header" in v.message.lower() for v in result.violations)

    def test_detects_bold_text(self):
        """Bold markdown should be detected in plain-text grants."""
        content = "This has **bold text** in it."

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("bold" in v.message.lower() for v in result.violations)

    def test_detects_italic_text(self):
        """Italic markdown should be detected in plain-text grants."""
        content = "This has *italic text* in it."

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("italic" in v.message.lower() or "emphasis" in v.message.lower()
                   for v in result.violations)

    def test_detects_markdown_links(self):
        """Links should be detected in plain-text grants."""
        content = "Check out [this link](https://example.com) for more info."

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("link" in v.message.lower() for v in result.violations)

    def test_detects_code_blocks(self):
        """Code blocks should be detected in plain-text grants."""
        content = """Some text.

```python
def hello():
    print("world")
```

More text."""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("code" in v.message.lower() for v in result.violations)

    def test_detects_inline_code(self):
        """Inline code should be detected in plain-text grants."""
        content = "Use the `print()` function."

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("code" in v.message.lower() for v in result.violations)

    def test_detects_html_comments(self):
        """HTML comments should be detected in plain-text grants."""
        content = """Some text.

<!-- This is a comment -->

More text."""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("comment" in v.message.lower() or "html" in v.message.lower()
                   for v in result.violations)

    def test_allows_plain_text(self):
        """Plain text without markdown should pass validation."""
        content = """This is plain text content.

It has multiple paragraphs separated by blank lines.

It mentions things like PolicyEngine and dates like 2026, but no markdown formatting."""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert result.passed
        assert len(result.violations) == 0

    def test_allows_markdown_when_accepts_markdown_true(self):
        """Markdown should be allowed when accepts_markdown is True."""
        content = """## Header

This has **bold** and *italic* text.

| Col 1 | Col 2 |
|-------|-------|
| A     | B     |
"""

        validator = MarkdownContentValidator(accepts_markdown=True)
        result = validator.validate_content(content, "test.md")

        assert result.passed
        assert len(result.violations) == 0

    def test_allows_urls_in_plain_text(self):
        """URLs without markdown link syntax should be allowed."""
        content = "Visit https://example.com for more information."

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        # Plain URLs are OK - it's the markdown link syntax that's the problem
        assert result.passed

    def test_detects_bullet_lists(self):
        """Markdown bullet lists should be detected in plain-text grants."""
        content = """Here are some items:

- First item
- Second item
- Third item
"""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("list" in v.message.lower() for v in result.violations)

    def test_detects_numbered_lists(self):
        """Markdown numbered lists should be detected in plain-text grants."""
        content = """Here are some steps:

1. First step
2. Second step
3. Third step
"""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any("list" in v.message.lower() for v in result.violations)

    def test_violation_includes_line_number(self):
        """Violations should include line numbers for easy fixing."""
        content = """Line one.
Line two.
## Header on line three
Line four."""

        validator = MarkdownContentValidator(accepts_markdown=False)
        result = validator.validate_content(content, "test.md")

        assert not result.passed
        assert any(v.line_number == 3 for v in result.violations)

    def test_validates_directory(self):
        """Should validate all markdown files in a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create responses directory
            responses_dir = tmppath / "responses"
            responses_dir.mkdir()

            # Write a file with markdown
            (responses_dir / "a_intro.md").write_text("## Bad Header\n\nContent here.")

            # Write a file without markdown
            (responses_dir / "b_summary.md").write_text("This is plain text.\n\nMore text.")

            validator = MarkdownContentValidator(accepts_markdown=False)
            result = validator.validate_directory(responses_dir)

            assert not result.passed
            # Only the file with markdown should have violations
            assert any("a_intro.md" in v.file_path for v in result.violations)
            assert not any("b_summary.md" in v.file_path for v in result.violations)


class TestMarkdownValidationIntegration:
    """Integration tests for markdown validation with grant.yaml."""

    def test_reads_accepts_markdown_from_grant_yaml(self):
        """Should read accepts_markdown setting from grant.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create grant.yaml with accepts_markdown: false
            grant_yaml = tmppath / "grant.yaml"
            grant_yaml.write_text(yaml.dump({
                "full_application": {
                    "title": "Test Grant",
                    "funder": "Test Funder",
                    "accepts_markdown": False,
                }
            }))

            # Create responses with markdown
            responses_dir = tmppath / "responses"
            responses_dir.mkdir()
            (responses_dir / "test.md").write_text("## Has markdown header")

            validator = MarkdownContentValidator.from_grant_yaml(grant_yaml)
            result = validator.validate_directory(responses_dir)

            assert not result.passed

    def test_defaults_to_accepting_markdown(self):
        """Should default to accepting markdown if not specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create grant.yaml without accepts_markdown
            grant_yaml = tmppath / "grant.yaml"
            grant_yaml.write_text(yaml.dump({
                "full_application": {
                    "title": "Test Grant",
                    "funder": "Test Funder",
                }
            }))

            # Create responses with markdown
            responses_dir = tmppath / "responses"
            responses_dir.mkdir()
            (responses_dir / "test.md").write_text("## Has markdown header")

            validator = MarkdownContentValidator.from_grant_yaml(grant_yaml)
            result = validator.validate_directory(responses_dir)

            # Should pass because markdown is allowed by default
            assert result.passed

"""Text processing utilities."""

import re
from typing import List, Tuple


def count_words(text: str) -> int:
    """Count words in text, handling markdown markup appropriately.

    Removes markdown formatting and counts actual words that would appear
    in the final document.
    """
    if not text:
        return 0

    # Remove markdown links but keep link text
    clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Remove markdown formatting characters
    clean = re.sub(r"[*_`#]", "", clean)

    # Remove HTML tags if present
    clean = re.sub(r"<[^>]+>", "", clean)

    # Normalize whitespace
    clean = re.sub(r"\s+", " ", clean).strip()

    return len(clean.split()) if clean else 0


def clean_markdown(text: str) -> str:
    """Clean markdown text for processing while preserving structure."""
    # Remove excessive whitespace but preserve paragraph breaks
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped or (cleaned_lines and cleaned_lines[-1]):  # Keep structure
            cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines)


def extract_headings(text: str) -> List[Tuple[int, str]]:
    """Extract headings from markdown text.

    Returns:
        List of (level, title) tuples where level is 1-6
    """
    headings = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        headings.append((level, title))
    return headings


def estimate_pages(text: str, words_per_page: int = 250) -> int:
    """Estimate number of pages for text."""
    word_count = count_words(text)
    return max(1, (word_count + words_per_page - 1) // words_per_page)


def truncate_text(text: str, max_words: int) -> str:
    """Truncate text to maximum word count."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def validate_text_content(text: str) -> List[str]:
    """Basic text content validation.

    Returns list of issues found.
    """
    issues = []

    if not text.strip():
        issues.append("Content is empty")
        return issues

    # Check for common issues
    if len(text) < 50:
        issues.append("Content appears very short")

    # Check for placeholder text
    placeholders = ["lorem ipsum", "placeholder", "todo", "tbd", "xxx"]
    text_lower = text.lower()
    for placeholder in placeholders:
        if placeholder in text_lower:
            issues.append(f"Placeholder text found: '{placeholder}'")

    # Check for repeated words (might indicate copy-paste errors)
    words = re.findall(r"\b\w+\b", text.lower())
    word_counts = {}
    for word in words:
        if len(word) > 3:  # Only check longer words
            word_counts[word] = word_counts.get(word, 0) + 1

    # Flag words that appear unusually often
    total_words = len(words)
    if total_words > 0:
        for word, count in word_counts.items():
            if count > max(
                3, total_words * 0.02
            ):  # >2% of text or more than 3 times
                issues.append(
                    f"Word '{word}' appears {count} times (may be excessive)"
                )

    return issues

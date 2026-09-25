"""Citation extraction and syntax validation regression tests."""

from grantkit.references.citation_extractor import CitationExtractor


def test_grouped_pandoc_citations_are_valid():
    text = "Evidence supports the claim [@first2026; @second2025]."

    extractor = CitationExtractor()

    assert extractor.validate_citation_syntax(text) == []
    assert [
        citation.citation_key
        for citation in extractor.extract_citations_from_text(text)
    ] == ["first2026", "second2025"]


def test_bare_pandoc_key_is_reported_but_email_is_not():
    text = "See @first2026. Contact grants@example.org for details."

    issues = CitationExtractor().validate_citation_syntax(text)

    assert issues == ["Line 1: Bare @ symbol without brackets"]


def test_plain_bracket_labels_are_not_citations():
    text = "See [Figure], [Appendix], and [TBD] before submission."

    citations = CitationExtractor().extract_citations_from_text(text)

    assert citations == []

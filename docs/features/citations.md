# Citation management

GrantKit uses pandoc-style `[@key]` citations backed by a `references.bib`
BibTeX database. `grantkit check` verifies that every citation resolves.

## How it flows

1. **Response files** use `[@key]` citation syntax.
2. **references.bib** holds the BibTeX database.
3. **`grantkit check`** extracts every `[@key]` and reports any that don't
   resolve against `references.bib` (`unresolved_citation`), plus malformed
   citation syntax (`citation_syntax`) and citations used with no bib present
   (`missing_references_bib`).
4. **`grantkit build`** assembles the sections; your BibTeX travels with the
   project in git.

## references.bib

Create a `references.bib` in the grant directory (a fresh `grantkit init`
scaffolds an empty one):

```bibtex
@article{smith_example_2024,
  title = {An Example Research Article},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Examples},
  year = {2024},
  doi = {10.1000/example.doi}
}

@techreport{treasury_report_2024,
  title = {Government Policy Report},
  author = {{HM Treasury}},
  institution = {HM Treasury},
  year = {2024}
}
```

### Institutional authors

Wrap organization names in double braces so they aren't split into first/last
names:

```bibtex
author = {{HM Treasury}}
author = {{PolicyEngine}}
author = {{National Science Foundation}}
```

A double-braced name prints whole ("National Science Foundation", not
"Foundation, National Science") and sorts under its first word, as in BibTeX.
Single braces (`author = {National Science Foundation}`) are ordinary name
syntax, so the last word is read as a surname.

## Using citations

```markdown
Recent research shows a significant impact [@smith_example_2024].

Multiple sources confirm this [@smith_example_2024; @doe_study_2023].
```

Don't hardcode `(Smith, 2024)` — use the key so the linter can verify it and
tools can render it consistently.

## Checking citations

```bash
grantkit check
```

Relevant findings:

| Rule | Level | Meaning |
|------|-------|---------|
| `unresolved_citation` | error | A `[@key]` with no entry in `references.bib`. |
| `missing_references_bib` | warning | Citations are used but no `references.bib` was found. |
| `citation_syntax` | warning | Malformed citation syntax (e.g. an unclosed bracket). |

## Programmatic use

```python
from grantkit.references import BibTeXManager, CitationExtractor

manager = BibTeXManager("path/to/grant")
manager.load_bibliography()
keys = manager.get_all_keys()

used = CitationExtractor().extract_citations_from_text(text)
missing = {c.citation_key for c in used} - keys
```

### Numbering a multi-document proposal

`BibliographyGenerator` turns `[@key]` citations into numbers (`[12]`) and
writes a numbered References Cited list. NSF proposals are several documents
(Project Summary, Project Description, References Cited) that must share **one**
numbering, so number them all from one key list:

```python
from grantkit.references import BibliographyGenerator

gen = BibliographyGenerator("path/to/grant")

# One call: every document numbered from the union of their keys.
(summary_out, description_out), order = gen.process_documents_with_citations(
    [summary, description]
)
refs = gen.create_separate_references_document(
    summary + "\n" + description, citation_order=order
)

# Or build the order once and number each document separately, even in
# separate processes: the order is the same everywhere.
order = gen.citation_order([summary, description])
summary_out, _ = gen.process_content_with_citations(summary, citation_order=order)
```

`process_content_with_citations(text)` without `citation_order` numbers only
the keys that one text cites, so a Summary citing a subset would get different
numbers from the Description. Passing an order that lacks a key the text cites
raises `ValueError` rather than leaving that citation unnumbered.

The alphabetical order sorts by the first author's surname (an institution's
whole name), then breaks ties by the full author list, year, title, and finally
the citation key. It never depends on Python's per-process hash seed, so every
run numbers the same keys the same way. A key missing from `references.bib`
keeps its number and gets a "Missing entry" line in References Cited, so later
numbers never shift.

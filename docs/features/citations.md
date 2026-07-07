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
```

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

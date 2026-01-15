# Citation Management

GrantKit supports BibTeX-based citation management with automatic rendering in the web app.

## Overview

Citations flow through GrantKit as follows:

1. **Source files** use pandoc-style `[@key]` citation syntax
2. **references.bib** contains the BibTeX database
3. **`grantkit sync push`** parses the BibTeX and syncs entries to the database
4. **Web app** renders citations as `(Author, Year)` with hover tooltips

## BibTeX File

Create a `references.bib` file in your grant directory:

```bibtex
@article{smith_example_2024,
  title = {An Example Research Article},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Examples},
  volume = {42},
  pages = {1--15},
  year = {2024},
  doi = {10.1000/example.doi}
}

@techreport{treasury_report_2024,
  title = {Government Policy Report},
  author = {{HM Treasury}},
  institution = {HM Treasury},
  year = {2024},
  url = {https://example.gov.uk/report}
}

@misc{organization_2024,
  title = {Organization Website},
  author = {{Organization Name}},
  year = {2024},
  url = {https://example.org}
}
```

### Citation Keys

Use descriptive keys following the pattern: `author_topic_year`

- `smith_example_2024` - Single author
- `treasury_report_2024` - Government body
- `policyengine_budget_2024` - Organization

### Institutional Authors

For organizations, wrap the name in double braces to prevent parsing as individual names:

```bibtex
author = {{HM Treasury}}
author = {{PolicyEngine}}
author = {{Institute for Fiscal Studies}}
```

## Using Citations in Responses

In your markdown response files, use pandoc-style citations:

```markdown
Recent research shows significant impact [@smith_example_2024].

The government has acknowledged this [@treasury_report_2024].

Multiple sources confirm these findings [@smith_example_2024; @doe_study_2023].
```

### What NOT to do

Don't hardcode citations:

```markdown
<!-- BAD - hardcoded -->
Recent research (Smith, 2024) shows significant impact.

<!-- GOOD - use citation key -->
Recent research [@smith_example_2024] shows significant impact.
```

## Syncing to Database

When you run `grantkit sync push`, the BibTeX file is automatically parsed and synced:

```bash
$ grantkit sync push -g my-grant

Push complete!
   Grants: 1
   Responses: 12
   Bibliography entries: 15
```

## Web App Rendering

In the GrantKit web app:

1. **Display**: Citations render as `(Smith, 2024)` or `(Smith & Doe, 2024)` or `(Smith et al., 2024)`
2. **Tooltips**: Hover over a citation to see the full reference
3. **Copy**: The copy button renders citations inline for pasting into submission portals

### Example Rendering

| Source | Rendered |
|--------|----------|
| `[@smith_example_2024]` | (Smith, 2024) |
| `[@smith_example_2024; @doe_study_2023]` | (Smith, 2024; Doe, 2023) |
| `[@treasury_report_2024]` | (HM Treasury, 2024) |

## Auto-Generated Bibliography

For sections that should display a bibliography (like "References Cited"), the app can auto-generate the list from all citations used across the grant's responses.

## Validation

Check for citation issues:

```bash
# Check all citations have matching BibTeX entries
grantkit check-citations -g my-grant
```

## Database Schema

Bibliography entries are stored in the `bibliography_entries` table:

| Column | Type | Description |
|--------|------|-------------|
| grant_id | text | Associated grant |
| citation_key | text | BibTeX key (e.g., "smith_example_2024") |
| entry_type | text | article, book, techreport, misc, etc. |
| title | text | Publication title |
| authors | jsonb | Array of author names |
| year | text | Publication year |
| journal | text | Journal name (for articles) |
| url | text | URL if available |
| doi | text | DOI if available |

## Migration

If you have existing hardcoded citations, you can convert them:

1. Create corresponding BibTeX entries in `references.bib`
2. Replace hardcoded `(Author, Year)` with `[@key]`
3. Run `grantkit sync push` to sync bibliography

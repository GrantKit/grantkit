# check — the linter

```bash
grantkit check [--json] [--strict] [--urls] [PATH]
```

`check` runs every applicable linter against the grant and prints the findings
as errors and warnings. It exits non-zero when there are errors — so it drops
straight into CI or a pre-submission gate.

## Options

| Option | Description |
|--------|-------------|
| `--json` | Emit the findings as JSON (the `checks` block of `status.json`). |
| `--strict` | Treat warnings as failures too (non-zero exit on any warning). |
| `--urls` | Also verify that URLs resolve. This is the only check that touches the network. |

## What is checked

| Rule id (examples) | Level | Description |
|--------------------|-------|-------------|
| `required_section_missing`, `required_section_empty` | error | Required sections must exist and have content. |
| `word_limit_exceeded`, `char_limit_exceeded` | error | Word/character limits from `grant.yaml`. |
| `page_limit_estimate_exceeded` | warning | Rough page estimate over the limit (confirm in the built PDF). |
| `placeholder_text` | warning | `[TO BE COMPLETED]`, `TODO`, `lorem ipsum`, etc. |
| `markdown_in_plain_text` | error | Markdown used where the portal accepts plain text only. |
| `unresolved_citation` | error | A `[@key]` that isn't in `references.bib`. |
| `missing_references_bib`, `citation_syntax` | warning | Citations used with no bib, or malformed citation syntax. |
| `budget_inconsistency` | warning | Fringe/indirect totals don't match their rates. |
| `budget_over_total_cap`, `budget_over_annual_cap` | error | Budget exceeds a funder cap from the rule pack. |
| `salary_above_market`, `salary_market_check` | error/warning | BLS OEWS salary sanity (only when `BLS_API_KEY` is set). |
| `nsf_compliance`, `nsf_missing_intellectual_merit`, … | error/warning | NSF PAPPG content engine (prohibited URLs/emails, required statements). |
| `spelling_locale` | warning | US spelling in an en-GB grant (or vice versa). |
| `dead_url` | warning | URL didn't resolve (`--urls` only). |

Which rules apply depends on the funder [rule pack](../packs.md): the NSF
content engine runs only for packs with `content_engine: nsf_pappg`, the
plain-text check runs only when the portal is plain-text, and so on.

## Budget checks

If a `budget.yaml` is present, `check` computes its totals and flags:

- arithmetic inconsistencies (a stated fringe or indirect that doesn't match
  `rate × base`), and
- funder cap violations, using `budget_rules.total_cap` / `annual_cap` from the
  rule pack.

BLS salary and GSA per-diem lookups run only when `BLS_API_KEY` / `GSA_API_KEY`
are set in the environment (they make network calls), so `check` stays fully
offline by default.

## Example

```bash
$ grantkit check
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Level   ┃ Rule                ┃ Section  ┃ Message                   ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ error   │ word_limit_exceeded │ methods  │ 3120 words exceeds the... │
│ warning │ spelling_locale     │ summary  │ 'color' (line 4) is not.. │
└─────────┴─────────────────────┴──────────┴───────────────────────────┘

1 error(s), 1 warning(s).
$ echo $?
1
```

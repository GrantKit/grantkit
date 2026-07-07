# Artifacts

GrantKit writes three machine-readable artifacts. `status.json` is the stable
public contract other tools depend on; `assembled.html` and `check.json` are
convenience outputs.

## status.json

Written by `grantkit status --json` and always by `grantkit build`, into the
grant project root. It is the canonical, versioned description of a proposal's
state — completion, per-section word counts, and the current lint results.
External consumers (dashboards, the PolicyEngine/CRM viewing surface, agents)
should treat this file as the API.

### Shape

```json
{
  "grantkit_version": "0.2.0",
  "generated_at": "2026-07-07T12:00:00+00:00",
  "grant": {
    "title": "PolicyEngine UK",
    "funder": "Nuffield Foundation",
    "program": "Research, Development and Analysis Fund",
    "deadline": "2026-01-14"
  },
  "completion": {
    "sections_total": 14,
    "sections_complete": 9,
    "words_total": 6421,
    "percent": 64.3
  },
  "sections": [
    {
      "id": "project_summary",
      "title": "Project Summary",
      "words": 240,
      "word_limit": 250,
      "status": "complete",
      "issues": []
    }
  ],
  "checks": {
    "errors": 0,
    "warnings": 2,
    "items": [
      {
        "level": "warning",
        "rule": "placeholder_text",
        "message": "'J) Timetable' still contains placeholder text: [TO BE COMPLETED].",
        "section": "j_timetable",
        "citation": null
      }
    ]
  }
}
```

### Fields

| Path | Type | Description |
|------|------|-------------|
| `grantkit_version` | string | GrantKit version that produced the file (semver). |
| `generated_at` | string | ISO 8601 timestamp (UTC, with offset). |
| `grant.title` | string | Proposal title (may be empty). |
| `grant.funder` | string | Funder name. |
| `grant.program` | string | Program / solicitation. |
| `grant.deadline` | string | `YYYY-MM-DD`, or `""` if unset. |
| `completion.sections_total` | int | Number of sections defined. |
| `completion.sections_complete` | int | Sections with `status == "complete"`. |
| `completion.words_total` | int | Sum of section word counts. |
| `completion.percent` | float | `sections_complete / sections_total * 100`, one decimal. |
| `sections[].id` | string | Stable section id. |
| `sections[].title` | string | Human title. |
| `sections[].words` | int | Word count (Markdown markup stripped). |
| `sections[].word_limit` | int \| null | Limit from `grant.yaml`, or `null`. |
| `sections[].status` | enum | One of `complete`, `partial`, `empty`, `over_limit`. |
| `sections[].issues` | string[] | Human-readable per-section notes (limits, placeholders). |
| `checks.errors` | int | Number of error-level findings. |
| `checks.warnings` | int | Number of warning-level findings. |
| `checks.items[].level` | enum | `error` or `warning`. |
| `checks.items[].rule` | string | Stable rule id (e.g. `word_limit_exceeded`). |
| `checks.items[].message` | string | Human-readable description. |
| `checks.items[].section` | string \| null | Section id the finding belongs to, or `null`. |
| `checks.items[].citation` | string \| null | Source citation (e.g. a PAPPG reference) or `null`. |

### Section status values

| Status | Meaning |
|--------|---------|
| `complete` | Non-empty, within limits, no placeholder text. |
| `partial` | Non-empty but contains placeholder text. |
| `empty` | No content (missing file or zero words). |
| `over_limit` | Exceeds its word or character limit. |

### Compatibility

- New **top-level keys**, **section keys**, and **check-item keys** may be
  added in minor releases; consumers should ignore unknown keys.
- The four `sections[].status` values and the two `checks.items[].level`
  values are stable within a major version.
- `rule` ids are stable; new rules may appear. Match on the ids you care about
  and treat unknown rules generically (by `level`).

## assembled.html

Written by `grantkit build --share`. A single self-contained (no external
assets) HTML review page: per-section cards with word counts and status
badges, a completion summary, deadline countdown, and the list of check
findings. Safe to publish as a CI artifact or open locally.

## check.json

Not written by the CLI directly, but produced in CI by
`grantkit check --json > check.json`. It is exactly the `checks` block of
`status.json`:

```json
{ "errors": 0, "warnings": 2, "items": [ ... ] }
```

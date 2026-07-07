# Funder rule packs

A **rule pack** is a declarative YAML file describing everything the engine
needs to lint and scaffold a grant for one funder: its sections and limits,
formatting rules (each with a citation), budget caps, portal quirks, spelling
locale, and review rubric. Packs live under `grantkit/data/funders/`; the stem
of the filename is the pack id (`nsf-pappg.yaml` → `nsf-pappg`).

## Packs that ship today

| Pack id | Funder | Notes |
|---------|--------|-------|
| `nsf-pappg` | National Science Foundation | PAPPG 24-1; full content engine + merit-review rubric. |
| `nuffield-rda` | Nuffield Foundation | RDA full application; `en-GB`; plain-text portal. |
| `pbif` | Public Benefit Innovation Fund | Section list only; no limits are published. |

## Using a pack

`grantkit init --funder <id>` scaffolds from a pack. At runtime a grant is
matched to a pack by its `pack:` field, then by funder name.

## Schema

The full schema is documented in `grantkit/packs/schema.py`. Top-level keys:

| Key | Type | Notes |
|-----|------|-------|
| `id` | string, required | Matches the filename stem. |
| `name` | string, required | Funder name. |
| `program` | string | Default program/solicitation. |
| `version` | string | Funder-guidance version (e.g. PAPPG `24-1`). |
| `source_url` | string | Canonical solicitation/policy URL. |
| `locale` | `en-US` \| `en-GB` | Spelling locale enforced by `check`. |
| `provenance` | string | How the pack's values were sourced. |
| `content_engine` | `nsf_pappg` \| null | A named programmatic content checker. |
| `sections` | list | `id`/`title`/`word_limit`/`char_limit`/`page_limit`/`required`/`description`/`file`. |
| `formatting_rules` | list | `id`/`description`/`severity`/`citation`/`url`/`quote`/`applies_to`. |
| `budget_rules` | mapping | `total_cap`/`annual_cap`/`indirect_rate_max`/`mtdc_excludes`/`currency`. |
| `portal` | mapping | `accepts_markdown`/`plain_text_boxes`/`url`. |
| `review_rubric` | list | Assessment criteria for `grantkit review`. |

## Contributing a pack

1. **Copy** an existing pack and rename it to `<funder>.yaml`.
2. **Only encode what you can source.** Leave a limit `null` if the funder does
   not publish one — never invent a number. Absence of a limit is *unknown*,
   not *unlimited*.
3. **Record provenance.** Add a `provenance:` field and inline comments citing
   where each value came from (URL, solicitation, or a reference application).
4. **Set the essentials:** `locale` and `portal.accepts_markdown` drive the
   spelling and plain-text checks.
5. **Cite formatting rules.** Every `formatting_rules` entry should carry a
   `citation` (and ideally a `url` and verbatim `quote`).
6. **Validate and test:**

   ```bash
   python -c "from grantkit.packs import load_pack; load_pack('your-pack')"
   ```

   `load_pack` validates against the schema and raises on any error. Add a case
   to `tests/test_packs.py` asserting your sourced values.

## Content engines

Most formatting rules are documentation the linter surfaces but cannot verify
from Markdown (font size, margins — these are PDF-level). A pack can opt into a
**content engine** — a named programmatic checker — via `content_engine`.
Today the only engine is `nsf_pappg`, which runs the NSF PAPPG content
validator (prohibited URLs/emails, required Intellectual Merit / Broader
Impacts statements, non-ASCII detection) over the response sections.

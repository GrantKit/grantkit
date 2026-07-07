# Changelog

All notable changes to GrantKit are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-07-07

Fixes from the first two real-application runs (PBIF round 2, Nuffield
rapid-response).

### Added

- Per-section `format: prose|fields`. `fields` sections hold individual portal
  form values (Field/Value tables typed one by one), so plain-text portal
  linting skips them and `build` renders them verbatim as an on-screen
  reference instead of a paste block.
- Placeholder detection catches bracketed directives such as
  `[MAX: phone number]`, `[AK: confirm]`, and `[NEED INPUT]`.
- Composite GitHub Action gains an `install-spec` input for installing from a
  pinned version or git ref.

### Changed

- `markdown_in_plain_text` severity now tracks build convertibility: headers,
  emphasis, links, and inline code are warnings (they are stripped cleanly in
  the built copy blocks — paste from the build output); tables and HTML
  comments remain errors.
- `_to_plaintext` strips HTML comments from portal copy blocks.
- Unparseable `budget.yaml` now reports an actionable `budget_schema_mismatch`
  warning instead of a raw exception message.

## [0.2.0] - 2026-07-07

Rebuilt GrantKit as a stateless, local-first engine — "the linter and compiler
for grant proposals." The Supabase-backed sync application is retired; the
engine reads files and writes files, and makes no AI calls.

### Added

- **Check runner** (`grantkit check`) consolidating every linter behind one API:
  required sections, word/character/page limits, placeholder detection, Markdown
  validity, plain-text-portal enforcement, citation resolution against
  `references.bib`, budget arithmetic and funder caps, the NSF PAPPG content
  engine, US/UK spelling locale, and opt-in URL liveness (`--urls`). Errors vs.
  warnings, with non-zero exit on errors (warnings fail only with `--strict`).
- **Funder rule packs** (`grantkit/data/funders/*.yaml`) with a documented
  schema and validation: `nsf-pappg`, `nuffield-rda`, `pbif`.
- **`status.json` contract** — a stable machine-readable artifact written by
  `grantkit status --json` and every `grantkit build`. Documented in
  `docs/artifacts.md`.
- **`grantkit build`** — compile responses to `md`/`html`/`pdf`/`docx`, with
  plain-text copy blocks for plain-text portals and a `--share` review page.
- **`grantkit review`** — a structured review packet for an AI agent (no AI
  calls).
- **`grantkit init`** — scaffold a project from a funder pack.
- **MCP server** (`grantkit-mcp`, optional `[mcp]` extra) exposing
  `grant_check` / `grant_status` / `grant_build`.
- **GitHub Action** (`action.yml`) — "CI for grants": lint, build the review
  page, and upload `status.json` as artifacts.

### Changed

- The CLI is now exactly five verbs: `init`, `check`, `build`, `review`,
  `status`.
- README, docs, and bundled `.claude/` skills rewritten for the engine.
- `pyproject`: added `docx` and `mcp` extras and the `grantkit-mcp` script.

### Removed

- Supabase sync, OAuth authentication, and all `sync`/`auth` commands.
- The `ai` extra (anthropic/openai) — the engine makes no AI calls by design.
- The beads (`bd`) issue tracker; work is tracked in GitHub Issues.

## [0.1.0]

- Initial release: NSF proposal assembly, validation, budget, and Supabase
  sync (retired in 0.2.0).

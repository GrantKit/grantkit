# Changelog

All notable changes to GrantKit are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Budget model** (`grantkit budget`, the sixth verb — agreed before
  being added). Compiles a proposal budget from three YAML documents: a
  priced work-item **menu** (`grantkit-menu/v0`), a **rates** contract
  from a rates provider (`grantkit-rates/v0`; eggnest-employer is the
  reference), and per-proposal **selections** over the menu
  (`grantkit-selection/v0`). Deterministic compile (labor from
  FTE-months x loaded rates, named unit costs, contracts, flat blocks,
  window-prorated recurring, fractional org base, single-application
  overhead honoring `overhead_included`), rich tables, `--json`,
  markdown `--output`, and a `--narrative` skeleton rendered from the
  compiled objects only.
- **Portfolio integrity gates** (`grantkit budget --check`, and inside
  `grantkit check` when `grant.yaml` binds a selection via
  `budget_model:`): schema validation for all three documents, unknown
  role/unit/item references, unresolved and cyclic dependencies,
  fraction ranges, duplicate lines, org-base typing, the **co-funding
  gate** (an item's fractions across live/awarded selections must not
  exceed 1), advisory rates heuristics (suspicious load factors,
  component sums that don't reconcile), an advisory target check, and
  funder caps from the bound rule pack applied to the compiled total.
- Docs: `docs/budget-model.md` and `docs/rates-contract.md`.
- `BibliographyGenerator.citation_order(documents)` and
  `process_documents_with_citations(documents)`, plus a `citation_order=`
  argument on `process_content_with_citations` and
  `create_separate_references_document`: number every document of a proposal
  (Summary, Description, References Cited) from one shared key list.

### Fixed

- **Citation numbering was nondeterministic.** The alphabetical sort keyed on
  the first author's surname only, and its input was `list(set(keys))`, so
  entries sharing a surname kept an order that changed with each process's
  string-hash seed. Documents numbered in separate processes could disagree:
  a submitted NSF Project Description cited 19 of its 48 references by the
  wrong number. Ties now break on the full author list, year, title, and key,
  and keys are de-duplicated in first-appearance order. **Numbers inside
  former tie blocks can change: re-render all documents of a proposal
  together.**
- Double-braced institutional authors (`{{National Science Foundation}}`) are
  no longer inverted to "Foundation, National Science" in References Cited,
  and sort under their full name, as the citation docs already promised.
- Author lists split on "and" across line breaks, as in BibTeX; a wrapped list
  no longer merges two authors into one.
- `.bib` files load in a fixed order (it was hash-randomized), so when a key
  is defined in more than one file the same entry wins every run, and a
  warning names the override. Each file gets a fresh parser: a reused one
  re-parsed every earlier file with each new one and emitted bibtexparser's
  "parser has been called more than once" warning, and under
  warnings-as-errors the second `.bib` file silently failed to load.
- The legacy PDF pipeline built References Cited from the already-numbered
  text, which has no `[@key]` left, so the list was always empty; it also
  numbered the text before loading `references.bib`, sorting by key instead of
  author. Both now use the order the text was numbered with.
- A key missing from `references.bib` keeps its number in References Cited
  (as a "Missing entry" line) instead of being dropped, which shifted every
  later number.
- Pin `bibtexparser<2`: 2.0 (2026-09-08) removed the 1.x API grantkit uses, so
  a fresh install failed on import.

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

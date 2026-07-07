# GrantKit

[![CI](https://github.com/GrantKit/grantkit/actions/workflows/ci.yml/badge.svg)](https://github.com/GrantKit/grantkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

**The linter and compiler for grant proposals.** Grants as files; agents bring the AI.

GrantKit is a stateless, local-first engine. It reads a `grant.yaml` plus your
Markdown responses and it lints them, compiles them into one submission
document, and reports a machine-readable status — with no cloud service and no
AI calls of its own. Point Claude Code (or any agent) at the files to do the
writing; GrantKit keeps them correct.

## Why files

Grant portals trap your content in web forms where your tools can't reach it.
GrantKit keeps the whole proposal as plain files in a git repo:

- **Agents read the full context** — every section, limit, and rule is on disk.
- **Changes are reviewable diffs**, not opaque form edits.
- **Git gives you history and rollback.**
- **You bring the AI you already use** — GrantKit itself calls no model.

Think of it as `eslint` + `tsc` for a grant: `grantkit check` is the linter,
`grantkit build` is the compiler, and funder **rule packs** are the config.

## Install

```bash
pip install grantkit               # core engine
pip install "grantkit[pdf]"        # + PDF output (WeasyPrint)
pip install "grantkit[docx]"       # + DOCX output (python-docx)
pip install "grantkit[mcp]"        # + MCP server for agents
pip install "grantkit[all]"        # everything
```

## Quickstart

```bash
# 1. Scaffold a project from a funder rule pack
grantkit init --funder nuffield-rda

# 2. Write — with Claude Code, Cursor, or your editor
claude "draft responses/b_case_for_importance.md from our repo README"

# 3. Lint against the funder's rules
grantkit check

# 4. Compile the submission document (+ a shareable review page)
grantkit build --format pdf --share
```

## The five verbs

| Verb | What it does |
|------|--------------|
| `grantkit init [--funder PACK]` | Scaffold `grant.yaml`, `responses/`, `budget.yaml`, `references.bib`. |
| `grantkit check [--json] [--strict] [--urls]` | Lint the proposal. Non-zero exit on errors (warnings fail only with `--strict`). |
| `grantkit build [--format md\|html\|pdf\|docx] [--share]` | Compile responses into one document; always writes `status.json`. |
| `grantkit review [--pack]` | Emit a structured review packet for an AI agent (no AI calls). |
| `grantkit status [--json]` | Completion %, per-section word counts, deadline countdown. |

Every verb takes an optional path to the grant directory (default `.`).

## What check catches

- Required sections present and non-empty; word / character / page limits.
- Placeholder text left behind (`[TO BE COMPLETED]`, `TODO`, `lorem ipsum`).
- Markdown that a **plain-text portal** would paste literally.
- Citations (`[@key]`) that don't resolve against `references.bib`.
- Budget arithmetic (fringe/indirect) and funder caps; optional BLS salary and
  GSA per-diem sanity when those API keys are set.
- Funder formatting rules from the rule pack — including the full NSF PAPPG
  content engine (prohibited URLs/emails, required Intellectual Merit / Broader
  Impacts, etc.).
- US/UK spelling for the funder's locale.
- Link liveness (`--urls`, opt-in — the only thing that touches the network).

## Funder rule packs

A **rule pack** is a YAML file under `grantkit/data/funders/` describing one
funder: its sections and limits, formatting rules (each with a citation),
budget caps, portal quirks, spelling locale, and review rubric. Three ship
today:

| Pack id | Funder | Notes |
|---------|--------|-------|
| `nsf-pappg` | National Science Foundation | PAPPG 24-1; full content engine + merit-review rubric. |
| `nuffield-rda` | Nuffield Foundation | RDA full application; en-GB; plain-text portal. |
| `pbif` | Public Benefit Innovation Fund | Section list only; no limits published. |

### Contributing a pack

1. Copy an existing pack in `grantkit/data/funders/` and edit it. The stem of
   the filename is the pack id (`acme-fund.yaml` → `acme-fund`).
2. Only encode values you can source. Leave a limit `null` if the funder
   doesn't publish one — never invent a number. Add a `provenance:` note and
   comments citing where each value came from.
3. Set `locale` (`en-US`/`en-GB`) and `portal.accepts_markdown`.
4. Run `python -c "from grantkit.packs import load_pack; load_pack('acme-fund')"`
   — it validates against the schema on load — and add a case to
   `tests/test_packs.py`.

The full schema is documented in `grantkit/packs/schema.py`.

## CI for grants

Add the composite action to lint every push and publish the review page and
`status.json` as build artifacts:

```yaml
# .github/workflows/grant.yml
name: Grant
on: [push, pull_request]
jobs:
  grantkit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: GrantKit/grantkit@v0.2.0
        with:
          path: .          # directory containing grant.yaml
          strict: "false"  # set "true" to fail on warnings too
```

Errors always fail the job; the `assembled.html` review page and `status.json`
are uploaded as artifacts on every run.

## MCP server for agents

Expose the engine to an agent over the Model Context Protocol:

```bash
pip install "grantkit[mcp]"
grantkit-mcp          # stdio transport
```

Tools: `grant_check(path)`, `grant_status(path)`, `grant_build(path, format)` —
each returning the same JSON structures the CLI emits.

## status.json

`grantkit build` and `grantkit status --json` always write a `status.json`
describing completion, per-section word counts, and the current check results.
It is GrantKit's stable, machine-readable contract for other tools (dashboards,
CRMs, agents). The exact shape is documented in
[docs/artifacts.md](docs/artifacts.md).

## Development

```bash
git clone https://github.com/GrantKit/grantkit.git
cd grantkit
pip install -e ".[dev]"

ruff check . && black --check . && mypy grantkit && pytest
```

Issues and tasks are tracked in
[GitHub Issues](https://github.com/GrantKit/grantkit/issues).

## License

MIT — see [LICENSE](LICENSE). Created by [PolicyEngine](https://policyengine.org).

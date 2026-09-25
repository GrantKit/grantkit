# GrantKit

**The linter and compiler for grant proposals.** Grants as files; agents bring
the AI.

GrantKit is a stateless, local-first engine. It reads a `grant.yaml` plus your
Markdown responses, then lints them, compiles them into one review document,
and reports a machine-readable status — with no cloud service and no
AI calls of its own. You point Claude Code (or any agent) at the files to do
the writing; GrantKit keeps them correct.

## Why files

- **Agents read the full context** — every section, limit, and rule is on disk.
- **Changes are reviewable diffs**, not opaque web-form edits.
- **Git gives you history and rollback.**
- **You bring the AI you already use** — GrantKit itself calls no model.

It is `eslint` + `tsc` for a grant: `grantkit check` is the linter,
`grantkit build` is the compiler, and funder rule packs are the config.

## Quick start

```bash
pip install grantkit

grantkit init --funder nuffield-rda   # scaffold from a funder pack
# ...write responses/ with your editor or an AI agent...
grantkit check                         # lint against funder rules
grantkit build --format pdf --share    # compile + shareable review page
```

## The six verbs

| Verb | What it does |
|------|--------------|
| `init` | Scaffold a grant project (optionally from a funder pack). |
| `check` | Lint the proposal; non-zero exit on errors. |
| `build` | Compile responses into one review document; always writes `status.json`. |
| `review` | Emit a review packet for an AI agent (no AI calls). |
| `status` | Completion %, per-section word counts, deadline countdown. |
| `budget` | Compile a budget from a priced work-item menu + rates + a selection. |

For NSF projects, `build --format pdf` produces a combined internal review
copy, not a Research.gov upload. Required sections must be uploaded or entered
separately, and raw `[@key]` citation markers are not rendered by `build`.

## Next steps

- [Getting started](getting-started.md)
- [CLI reference](cli/overview.md)
- [Funder rule packs](packs.md)
- [The budget model](budget-model.md) and [rates contract](rates-contract.md)
- [Artifacts and the status.json contract](artifacts.md)
- [MCP server and CI for grants](mcp-and-ci.md)

---

Created by [PolicyEngine](https://policyengine.org)

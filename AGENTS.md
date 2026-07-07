# Repository guidelines

## Issue tracking

Track work in **[GitHub Issues](https://github.com/GrantKit/grantkit/issues)**.
This project does not use beads (`bd`) or in-repo markdown task lists.

## Project overview

**GrantKit** — the linter and compiler for grant proposals. A stateless,
local-first engine: it reads a `grant.yaml` plus Markdown responses and lints,
compiles, and reports on them. It makes **no** AI calls and no network calls by
default (URL liveness and BLS/GSA lookups are opt-in and gated on flags/keys).

### Architecture

```
grantkit/
├── __init__.py        # package init, version, top-level exports
├── cli.py             # Click CLI — exactly five verbs
├── mcp_server.py      # FastMCP server (grantkit-mcp)
├── core/
│   ├── project.py     # GrantProject — reads grant.yaml + responses
│   ├── checks.py      # run_checks() — the consolidated linter
│   ├── status.py      # status.json contract
│   ├── scaffold.py    # `init`
│   ├── builder.py     # `build` (md/html/pdf/docx, --share)
│   ├── review.py      # `review` packet
│   ├── validator.py   # NSF PAPPG content validator
│   ├── assembler.py   # legacy assembler (retained)
│   └── spelling.py    # en-US / en-GB locale checks
├── packs/             # funder rule packs: schema, registry, loading
│   └── schema.py      # FunderPack schema + validate_pack()
├── data/funders/      # the rule packs (*.yaml); stem = pack id
├── budget/            # budget arithmetic, GSA per-diem, BLS OEWS salary
├── references/        # BibTeX + citation extraction
├── pdf/               # legacy NSF PDF pipeline (WeasyPrint), retained
└── utils/             # shared helpers
```

The five verbs are `init`, `check`, `build`, `review`, `status`. Do not add
top-level verbs without discussion — the surface is deliberately small.

## Build, test, and development commands

```bash
pip install -e ".[dev]"

pytest                        # all tests
pytest tests/test_checks.py   # one file
pytest -k spelling            # by pattern

ruff check --fix .            # lint (+ autofix)
black .                       # format (line length 79)
mypy grantkit                 # type check
```

### CI

Push / PR runs (`.github/workflows/ci.yml`): `ruff check .`,
`black --check .`, `mypy grantkit` (non-fatal), and `pytest`. Keep them green.

## Code style

- Python 3.12+, line length **79** (black + ruff configured).
- `snake_case` functions/modules, `PascalCase` classes, `UPPER_SNAKE`
  constants; imports sorted by ruff (isort).
- CLI output via `rich`; findings returned as `CheckItem`/`CheckResult`.

## Rule packs

- Live in `grantkit/data/funders/*.yaml`; the filename stem is the pack id.
- **Never invent limits.** Leave a value `null` if the funder doesn't publish
  it, and record `provenance`. Packs validate against `packs/schema.py` on
  load; add a case to `tests/test_packs.py` for any new pack.

## Commit & PR guidelines

- Conventional commits, imperative mood (`feat: add nih pack`).
- Run `ruff check . && black --check . && pytest` before pushing.
- PR descriptions: motivation, what changed, and test results.

## Environment variables

| Variable | Description |
|----------|-------------|
| `BLS_API_KEY` | Optional. Enables BLS OEWS salary checks in `grantkit check`. |
| `GSA_API_KEY` | Optional. Enables GSA per-diem lookups in budget costing. |

No other configuration is required — the engine is stateless and local-first.

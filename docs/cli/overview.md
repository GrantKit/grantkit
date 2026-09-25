# CLI overview

GrantKit has exactly six verbs. Each takes an optional path — the grant
directory (a folder containing `grant.yaml`), or for `budget` a
portfolio directory — defaulting to the current directory.

```bash
grantkit COMMAND [OPTIONS] [PATH]
```

| Command | Description |
|---------|-------------|
| [`init`](#init) | Scaffold a grant project (optionally from a funder pack). |
| [`check`](check.md) | Lint the proposal; non-zero exit on errors. |
| [`build`](build.md) | Compile responses into one review document; always writes `status.json`. |
| [`review`](#review) | Emit a review packet for an AI agent (no AI calls). |
| [`status`](#status) | Completion %, per-section word counts, deadline countdown. |
| [`budget`](#budget) | Compile a budget from a menu + rates + a selection. |

## init

```bash
grantkit init [--funder PACK_ID] [--force] [PATH]
```

Scaffolds `grant.yaml`, `responses/`, `budget.yaml`, and `references.bib`.
With `--funder`, sections and limits come from the named
[rule pack](../packs.md). `--force` overwrites an existing project.

## check

The linter. See [check](check.md).

```bash
grantkit check [--json] [--strict] [--urls] [PATH]
```

## build

The compiler. See [build](build.md).

```bash
grantkit build [--format md|html|pdf|docx] [--share] [--output PATH] [PATH]
```

## review

```bash
grantkit review [--pack] [--output FILE] [PATH]
```

Emits a JSON review packet — the funder's assessment rubric, the assembled
section content, and the current check results — for an AI agent to critique.
GrantKit makes no AI calls; it only builds the packet. `--pack` embeds the
full funder rule pack, not just the rubric. Pipe it straight to your agent:

```bash
grantkit review | claude -p "Review this proposal against the rubric."
```

## status

```bash
grantkit status [--json] [PATH]
```

Prints completion percentage, per-section word counts, and a deadline
countdown. `--json` writes (and prints) `status.json` — see
[artifacts](../artifacts.md).

## budget

```bash
grantkit budget [--selection ID | --combine ID1,ID2] [--check] [--json] [--output FILE] [--narrative] [PATH]
```

Compiles a portfolio selection — a proposal expressed as fractions of a
priced work-item menu — into budget tables, a markdown budget document
(`--output`), or structured JSON. `--check` runs the integrity gates
only, including the co-funding gate that errors when live or awarded
proposals sell the same item past 100%. PATH is a portfolio directory or a grant
project bound via `budget_model:`. See the
[budget model](../budget-model.md) and
[rates contract](../rates-contract.md).

`--combine` rolls up two or more packages into one funding-coverage view.
It stacks per-funder item and org-base shares, shows the unclaimed core-ops
gap, counts a shared org-base roster once, and runs C2 as though every chosen
package were live. It requires structured JSON and/or a Markdown output file;
single-selection output is unchanged.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (for `check`: no errors, or no warnings under `--strict`). A computable `budget --combine` scenario also succeeds when its only errors are embedded C2 over-allocation findings. |
| `1` | `check` found errors (or warnings under `--strict`); `budget --check` found errors; or budget compilation found a blocking structural error. |
| `2` | Usage error — e.g. no `grant.yaml`, unknown funder pack, missing format dependency, unreadable portfolio or unknown selection. |

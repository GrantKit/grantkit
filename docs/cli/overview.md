# CLI overview

GrantKit has exactly five verbs. Each takes an optional path to the grant
directory (a folder containing `grant.yaml`), defaulting to the current
directory.

```bash
grantkit COMMAND [OPTIONS] [PATH]
```

| Command | Description |
|---------|-------------|
| [`init`](#init) | Scaffold a grant project (optionally from a funder pack). |
| [`check`](check.md) | Lint the proposal; non-zero exit on errors. |
| [`build`](build.md) | Compile responses into one document; always writes `status.json`. |
| [`review`](#review) | Emit a review packet for an AI agent (no AI calls). |
| [`status`](#status) | Completion %, per-section word counts, deadline countdown. |

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

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (for `check`: no errors, or no warnings under `--strict`). |
| `1` | `check` found errors (or warnings under `--strict`). |
| `2` | Usage error — e.g. no `grant.yaml`, unknown funder pack, missing format dependency. |

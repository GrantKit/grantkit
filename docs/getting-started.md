# Getting started

This guide walks you from an empty directory to a linted, compiled proposal.

## Installation

```bash
pip install grantkit          # core engine
pip install "grantkit[pdf]"   # optional: PDF output (WeasyPrint)
pip install "grantkit[docx]"  # optional: DOCX output (python-docx)
```

GrantKit requires Python 3.12 or later.

## 1. Scaffold a project

```bash
grantkit init --funder nuffield-rda
```

This writes a self-contained project:

```
my-grant/
├── grant.yaml            # funder, program, deadline, section table
├── responses/            # one Markdown file per section
│   ├── project_summary.md
│   └── ...
├── budget.yaml           # empty, arithmetically-consistent skeleton
└── references.bib        # empty BibTeX file
```

Sections, word limits, spelling locale, and portal behaviour all come from the
funder rule pack. Run `grantkit init` without `--funder` for a generic
two-section skeleton.

## 2. Write

Each response is a Markdown file with optional YAML frontmatter (frontmatter is
ignored by the linter and the word count):

```markdown
---
title: Project Summary
word_limit: 250
status: draft
---

PolicyEngine democratizes policy analysis with free, open-source tools...
```

Edit these with your editor or an AI agent:

```bash
claude "draft responses/b_case_for_importance.md from our repo README"
```

## 3. Check

```bash
grantkit check
```

The linter reports errors and warnings — required sections, word/char/page
limits, placeholder text, citation resolution, budget arithmetic and funder
caps, funder formatting rules, and spelling locale. It exits non-zero on
errors (add `--strict` to fail on warnings too, or `--urls` to also verify
links resolve).

## 4. Track status

```bash
grantkit status            # human table + deadline countdown
grantkit status --json     # writes status.json (machine-readable)
```

## 5. Build

```bash
grantkit build --format pdf --share
```

`build` assembles every response into one document (`md`, `html`, `pdf`, or
`docx`). For plain-text portals it emits labelled copy blocks to paste box by
box. `--share` also writes a self-contained `assembled.html` review page, and
every build refreshes `status.json`.

## Next steps

- [CLI reference](cli/overview.md)
- [Funder rule packs](packs.md) — including how to contribute one
- [Artifacts and the status.json contract](artifacts.md)

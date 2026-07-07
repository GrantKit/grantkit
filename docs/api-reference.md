# API reference

GrantKit's engine is a small Python API. Everything the CLI does is available
programmatically, and nothing makes AI or (by default) network calls.

## Load a project

```python
from grantkit.core.project import GrantProject

project = GrantProject("path/to/grant")   # dir containing grant.yaml
project.title, project.funder, project.deadline
project.sections            # list[SectionState]
project.completion_percent  # float
```

Each `SectionState` carries `id`, `title`, `words`, `word_limit`,
`char_limit`, `page_limit`, `status` (`complete`/`partial`/`empty`/
`over_limit`), `placeholders`, and `issues`.

## Lint

```python
from grantkit.core.checks import run_checks

result = run_checks(project, strict=False, check_urls=False)
result.errors, result.warnings         # ints
result.failed(strict=False)            # bool
for item in result.items:
    print(item.level, item.rule, item.section, item.message)
result.to_dict()                       # {"errors", "warnings", "items": [...]}
```

## Status

```python
from grantkit.core.status import build_status, write_status

status = build_status(project)   # the status.json dict
write_status(project)            # writes status.json, returns its Path
```

The shape of `status` is the [status.json contract](artifacts.md).

## Build

```python
from grantkit.core.builder import build_project

result = build_project(project, fmt="pdf", share=True)
result.document_path   # proposal.pdf
result.share_path      # assembled.html (when share=True)
result.status_path     # status.json
```

## Review packet

```python
from grantkit.core.review import build_review

packet = build_review(project, include_pack=True)
packet["rubric"], packet["sections"], packet["checks"]
```

## Scaffold

```python
from grantkit.core.scaffold import init_project

created = init_project("new-grant", funder="nsf-pappg")  # list[Path]
```

## Rule packs

```python
from grantkit.packs import (
    list_pack_ids,
    load_pack,
    resolve_pack,
    validate_pack,
    load_pack_dict,
)

list_pack_ids()                         # ["nsf-pappg", "nuffield-rda", "pbif"]
pack = load_pack("nsf-pappg")           # FunderPack (validates on load)
resolve_pack("National Science Foundation").id   # "nsf-pappg"
validate_pack(load_pack_dict("pbif"))   # [] when valid
```

A `FunderPack` exposes `id`, `name`, `program`, `locale`, `accepts_markdown`,
`sections`, `formatting_rules`, `budget_rules`, `portal`, and `review_rubric`.

## Retained building blocks

These lower-level modules are still available and power the checks above:

- `grantkit.core.validator.NSFValidator` — the NSF PAPPG content validator.
- `grantkit.budget.BudgetCalculator` / `BudgetManager` — budget arithmetic,
  GSA per-diem, BLS OEWS salary validation.
- `grantkit.references.BibTeXManager` / `CitationExtractor` — bibliography and
  citation handling.
- `grantkit.pdf.PDFGenerator` — the legacy NSF PDF pipeline (WeasyPrint).

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
result.document_path   # proposal.pdf (a combined review copy for NSF)
result.share_path      # assembled.html (when share=True)
result.status_path     # status.json
result.warnings        # review/submission caveats surfaced by the builder
```

For NSF projects, the PDF uses current NSF-safe page and font defaults but is
explicitly a combined review copy, not a submission artifact. Upload or enter
the required sections separately in Research.gov. Citation markers remain raw
authoring text in this build.

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

## Budget model

```python
from grantkit.menu import (
    compile_combined,
    compile_selection,
    load_portfolio,
    run_combined_gates,
    run_gates,
)

portfolio = load_portfolio("org-portfolio")     # menu + rates + selections
findings = run_gates(portfolio)                 # list[CheckItem]
selection = portfolio.get_selection("oaif-2026")
cost = compile_selection(selection, portfolio)  # SelectionCost
cost.total_usd, cost.fit
cost.to_dict()

scenario_ids = ["funder-a", "funder-b"]
scenario_findings = run_combined_gates(portfolio, scenario_ids)
combined = compile_combined(portfolio, scenario_ids)  # CombinedCost
```

`run_gates(portfolio, selection_id=None, pack=None)` scopes the
per-selection gates to one selection when given an id, and applies a
`FunderPack`'s `budget_rules` caps to each compiled total when given a
pack. An id absent from the portfolio produces an `unknown_selection`
error finding. `compile_selection` assumes the gates passed — an unresolved
item, role, or unit raises `KeyError`; arithmetic outside the finite float
range is reported by `run_gates` as `budget_non_finite`. See the
[budget model](budget-model.md) and the
[rates contract](rates-contract.md).

`run_combined_gates` scopes the portfolio to the named selections and treats
all of them as live for the scenario. `compile_combined` returns the funding
stacks, org-base gap ledger, category totals, base-once staffing, and combined
revenue; callers can carry the separate findings alongside its `to_dict()`
output as the CLI does.

## Retained building blocks

These lower-level modules are still available and power the checks above:

- `grantkit.core.validator.NSFValidator` — the NSF PAPPG content validator.
- `grantkit.budget.BudgetCalculator` / `BudgetManager` — budget arithmetic,
  GSA per-diem, BLS OEWS salary validation.
- `grantkit.references.BibTeXManager` / `CitationExtractor` — bibliography and
  citation handling.
- `grantkit.pdf.PDFGenerator` — the legacy NSF PDF pipeline (WeasyPrint).

# build — the compiler

```bash
grantkit build [--format md|html|pdf|docx] [--share] [--output PATH] [PATH]
```

`build` assembles every response into one review document and always refreshes
`status.json`.

## Options

| Option | Description |
|--------|-------------|
| `--format` | Output format for the review document: `md` (default), `html`, `pdf`, or `docx`. NSF PDFs are review-only. |
| `--share` | Also write a self-contained `assembled.html` review page. |
| `--output PATH` | Path for the compiled review document (default `proposal.<format>`). |

## Formats

- **md** — one Markdown document (headings + section bodies). For plain-text
  portals (`accepts_markdown: false`) it instead emits labelled **copy blocks**
  with per-section word counts, ready to paste box by box.
- **html** — a styled, self-contained HTML document.
- **pdf** — requires the `pdf` extra (`pip install "grantkit[pdf]"`; WeasyPrint
  also needs the system Pango/Cairo libraries). NSF PDFs are combined review
  copies, not submission artifacts.
- **docx** — requires the `docx` extra (`pip install "grantkit[docx]"`).

Missing an optional dependency produces a clear message and a `2` exit code
rather than a stack trace.

## Outputs

| File | When |
|------|------|
| `proposal.<format>` | Always (the compiled review document). |
| `assembled.html` | With `--share` — a review page with per-section word counts and status badges. |
| `status.json` | Always — the machine-readable [status contract](../artifacts.md). |

## NSF PDF builds

For a project resolved to an NSF funder pack, the combined PDF uses Arial at
10 points, US Letter portrait pages, one-inch margins, a six-lines-per-inch
maximum, and no proposer-supplied page numbers. The PDF itself and the CLI both
display this warning:

> Review copy — not for NSF submission.

Research.gov collects proposal sections and attachments separately. Do not
upload the combined `proposal.pdf`; upload or enter each required section in
its corresponding Research.gov location. `build` also preserves citation
markers such as `[@key]` as raw authoring text. It does not resolve or format
them into submission-ready citations or a References Cited upload.

## Example

```bash
# Compile a combined PDF review copy and a shareable review page
grantkit build --format pdf --share

# Plain-text portal: get copy blocks to paste into each box
grantkit build --format md
```

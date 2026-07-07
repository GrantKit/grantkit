# build — the compiler

```bash
grantkit build [--format md|html|pdf|docx] [--share] [--output PATH] [PATH]
```

`build` assembles every response into one document and always refreshes
`status.json`.

## Options

| Option | Description |
|--------|-------------|
| `--format` | Output format: `md` (default), `html`, `pdf`, or `docx`. |
| `--share` | Also write a self-contained `assembled.html` review page. |
| `--output PATH` | Path for the compiled document (default `proposal.<format>`). |

## Formats

- **md** — one Markdown document (headings + section bodies). For plain-text
  portals (`accepts_markdown: false`) it instead emits labelled **copy blocks**
  with per-section word counts, ready to paste box by box.
- **html** — a styled, self-contained HTML document.
- **pdf** — requires the `pdf` extra (`pip install "grantkit[pdf]"`; WeasyPrint
  also needs the system Pango/Cairo libraries).
- **docx** — requires the `docx` extra (`pip install "grantkit[docx]"`).

Missing an optional dependency produces a clear message and a `2` exit code
rather than a stack trace.

## Outputs

| File | When |
|------|------|
| `proposal.<format>` | Always (the compiled document). |
| `assembled.html` | With `--share` — a review page with per-section word counts and status badges. |
| `status.json` | Always — the machine-readable [status contract](../artifacts.md). |

## Example

```bash
# Compile a PDF and a shareable review page
grantkit build --format pdf --share

# Plain-text portal: get copy blocks to paste into each box
grantkit build --format md
```

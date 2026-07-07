# PDF and DOCX output

`grantkit build` compiles your responses into one document. PDF and DOCX are
optional formats behind extras.

## Quick start

```bash
pip install "grantkit[pdf]"      # PDF (WeasyPrint)
pip install "grantkit[docx]"     # DOCX (python-docx)

grantkit build --format pdf --output proposal.pdf
grantkit build --format docx --output proposal.docx
```

If the extra isn't installed, `build` prints an actionable message and exits
with code `2` rather than a stack trace.

## How it works

`build` assembles every section (in `grant.yaml` order) into a single styled
HTML document, then renders it to PDF with WeasyPrint or to DOCX with
python-docx. For plain-text portals (`accepts_markdown: false`) it strips
Markdown so the output matches what the portal will accept.

For deep NSF PAPPG PDF compliance (embedded fonts, precise margins, separated
references) the lower-level `grantkit.pdf.PDFGenerator` pipeline is retained
and available programmatically.

## Page limits

`grantkit check` flags sections whose estimated page count exceeds their
`page_limit` (rule `page_limit_estimate_exceeded`). The estimate is a rough
words-per-page heuristic — always confirm the exact page count in the built
PDF before submitting.

## Citations

Citations use pandoc-style `[@key]` syntax resolved against `references.bib`.
`grantkit check` reports any `[@key]` with no matching entry
(`unresolved_citation`). See [Citation management](citations.md).

## Troubleshooting

**WeasyPrint won't import.** WeasyPrint needs system libraries in addition to
the Python package:

```bash
# macOS
brew install pango

# Ubuntu
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0
```

**Fonts.** Install standard serif fonts (e.g. `fonts-cmu` on Ubuntu,
`font-computer-modern` via Homebrew) for the closest match to NSF's expected
typography.

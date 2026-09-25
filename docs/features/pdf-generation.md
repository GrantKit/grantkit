# PDF and DOCX output

`grantkit build` compiles your responses into one review document. PDF and
DOCX are optional formats behind extras.

## Quick start

```bash
pip install "grantkit[pdf]"      # PDF (WeasyPrint)
pip install "grantkit[docx]"     # DOCX (python-docx)

grantkit build --format pdf --output proposal.pdf  # combined review copy
grantkit build --format docx --output proposal.docx
```

If the extra isn't installed, `build` prints an actionable message and exits
with code `2` rather than a stack trace.

## How it works

`build` assembles every section (in `grant.yaml` order) into a single styled
review document, then renders it to PDF with WeasyPrint or to DOCX with
python-docx. For plain-text portals (`accepts_markdown: false`) it strips
Markdown so the output matches what the portal will accept.

For NSF projects, the combined PDF is visibly labelled as an internal review
copy. It uses Arial at 10 points, US Letter portrait pages, one-inch margins,
no more than six lines per vertical inch, and no proposer-supplied page
numbers. Those formatting defaults do not turn the combined document into an
NSF submission artifact. Research.gov requires the applicable proposal
sections and attachments to be uploaded or entered separately.

The lower-level `grantkit.pdf.PDFGenerator` pipeline remains available
programmatically for specialized workflows, but callers must still map and
validate the resulting files against the applicable Research.gov upload
slots.

## Page limits

`grantkit check` flags sections whose estimated page count exceeds their
`page_limit` (rule `page_limit_estimate_exceeded`). The estimate is a rough
words-per-page heuristic. An NSF combined review PDF includes review-only
material and cannot establish the page count of any separate Research.gov
upload; render and validate each upload independently before submitting.

## Citations

Citations use pandoc-style `[@key]` syntax. `grantkit check` reports any
`[@key]` with no matching entry in `references.bib`
(`unresolved_citation`), but `grantkit build` does not resolve or format the
markers: they remain raw authoring text in its PDF and DOCX review outputs.
Prepare submission-ready inline citations and the References Cited upload
separately. See [Citation management](citations.md).

## Troubleshooting

**WeasyPrint won't import.** WeasyPrint needs system libraries in addition to
the Python package:

```bash
# macOS
brew install pango

# Ubuntu
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0
```

**Fonts.** The NSF review stylesheet requests Arial. Make sure Arial is
installed wherever WeasyPrint runs; font substitution can change layout and
is another reason to treat the combined output as review-only.

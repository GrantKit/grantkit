# PDF Generation

GrantKit generates NSF-compliant PDFs with proper fonts, margins, and formatting.

## Quick Start

```bash
grantkit pdf --output proposal.pdf
```

## Requirements

PDF generation requires additional dependencies:

```bash
pip install grantkit[pdf]
```

This installs:
- **WeasyPrint**: HTML-to-PDF rendering
- **Pygments**: Code syntax highlighting

Check your setup:

```bash
grantkit pdf-capabilities
```

## NSF Formatting Rules

GrantKit enforces NSF PAPPG requirements:

| Requirement | GrantKit Default |
|-------------|------------------|
| Font size | 11pt body, 10pt figures |
| Font family | Times New Roman, Computer Modern |
| Margins | 1 inch all sides |
| Line spacing | Single-spaced |
| Page size | 8.5" × 11" (US Letter) |

## Usage

### Basic PDF

```bash
grantkit pdf
```

Generates `proposal.pdf` from your markdown sections.

### Custom Output

```bash
grantkit pdf --output my-proposal.pdf
```

### Check Page Counts

```bash
grantkit check-pages
```

Output:

```
Page Count Summary
==================
Project Summary:     1 / 1  [OK]
Project Description: 12 / 15 [OK]
References:          3 / -  [OK]
Bio Sketches:        6 / 9  [OK] (3 people × 3 pages)
Budget Justification: 4 / 5  [OK]

Total: 26 pages
```

## Document Structure

GrantKit assembles PDFs from your project structure:

```
my-proposal/
├── sections/
│   ├── 01-summary.md
│   ├── 02-description.md
│   ├── 03-references.md
│   └── 04-bio-sketches.md
├── budget/
│   └── justification.md
└── proposal.yaml
```

## Citations and Bibliography

GrantKit supports BibTeX citations:

**In your markdown:**

```markdown
Previous work has shown significant effects [@smith2023; @jones2024].
```

**references.bib:**

```bibtex
@article{smith2023,
  author = {Smith, Jane},
  title = {Policy Effects Analysis},
  journal = {Journal of Policy},
  year = {2023}
}
```

Run citation check:

```bash
grantkit check-citations
```

## Export Formats

Besides PDF, you can export to DOCX:

```bash
grantkit export --format docx --output proposal.docx
```

Useful for collaborators who prefer Word.

## Troubleshooting

### WeasyPrint Not Found

```bash
pip install weasyprint
```

On macOS, you may also need:

```bash
brew install pango
```

### Font Issues

Install standard fonts:

```bash
# macOS
brew install --cask font-computer-modern

# Ubuntu
sudo apt-get install fonts-cmu
```

### Check Capabilities

```bash
grantkit pdf-capabilities
```

Shows which PDF features are available and any missing dependencies.

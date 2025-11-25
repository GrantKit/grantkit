# NSF-Compliant LaTeX Templates

This directory contains LaTeX templates optimized for NSF grant proposals.

## Templates

### nsf_optimized.tex
Space-optimized template that maximizes content while maintaining NSF compliance:
- Exactly 1-inch margins
- 11pt font (largest NSF-allowed size)  
- Optimized spacing and typography
- Smart hyphenation and widow/orphan control
- Smaller reference font when allowed

### nsf_standard.tex  
Standard template with normal spacing for comparison and fallback.

## Usage

Templates are automatically used by the PDF generator. You can also use them directly with pandoc:

```bash
pandoc proposal.md -o proposal.pdf --template nsf_optimized.tex --pdf-engine xelatex
```

## Customization

Templates support these variables:
- `title`: Document title
- `author`: Author name(s)
- `fontsize`: Font size (10pt or 11pt)
- `mainfont`: Font family (default: Times New Roman)
- `reference_font_size`: Smaller font for references
- Various spacing controls

## NSF Compliance

All templates ensure:
- Exactly 1-inch margins on all sides
- NSF-approved fonts (Times New Roman, Computer Modern)
- Single spacing (6 lines per inch maximum)
- Proper page numbering
- Professional appearance
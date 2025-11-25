# GrantKit

**Professional tools for grant proposal assembly, validation, and AI-assisted writing.**

GrantKit is an open-source CLI tool designed for researchers and grant writers who want programmatic control over their proposal workflow. It integrates seamlessly with AI assistants like Claude Code for rapid iteration.

## Why GrantKit?

- **Pre-submission validation** - Catch NSF PAPPG compliance issues before you submit
- **Programmatic workflow** - CLI-first design for automation and AI integration
- **Open source** - Inspect, modify, and extend to your needs
- **Multi-funder support** - Unified config format for NSF, Arnold Ventures, and more

## Quick Start

```bash
pip install grantkit

# Initialize a new NSF CSSI proposal
grantkit init cssi

# Check compliance
grantkit validate

# Generate PDF
grantkit pdf --optimize
```

## Features

| Feature | Description |
|---------|-------------|
| **Proposal Assembly** | Combine sections from markdown files into complete proposals |
| **NSF Validation** | Check formatting, page limits, URLs, citations against PAPPG |
| **Budget Management** | Calculate totals, GSA per diem lookups, indirect cost calculations |
| **PDF Generation** | NSF-compliant PDFs with proper fonts, margins, spacing |
| **Citation Management** | BibTeX integration with automatic bibliography |

## Documentation

- [Installation Guide](installation.md)
- [CLI Reference](cli.md)
- [Configuration](configuration.md)
- [Competitive Landscape](landscape.md)

## Links

- [GitHub Repository](https://github.com/grantkit/grantkit)
- [Issue Tracker](https://github.com/grantkit/grantkit/issues)
- [PyPI Package](https://pypi.org/project/grantkit/) *(coming soon)*

---

Created by [PolicyEngine](https://policyengine.org)

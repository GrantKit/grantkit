# GrantKit

**Professional tools for grant proposal assembly, validation, and AI-assisted writing.**

GrantKit is an open-source CLI designed for **AI-native teams** who use AI coding agents (Claude Code, Cursor) and want the same workflow for grant writing.

## Why GrantKit?

- **Supabase Sync** - Pull grants to local markdown, edit with AI, push back
- **Pre-submission validation** - Catch NSF PAPPG compliance issues before you submit
- **Salary validation** - Check personnel costs against BLS OEWS market data
- **Travel per diem** - Automatic GSA rate lookups by city and fiscal year
- **Open source** - Inspect, modify, and extend to your needs

## Quick Start

```bash
pip install grantkit

# Set up Supabase connection
export GRANTKIT_SUPABASE_KEY="your-key"

# Pull grants and responses to local markdown
grantkit sync pull

# Edit with your favorite AI tool
claude "improve the broader impacts section"

# Validate and push changes
grantkit validate
grantkit sync push
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `grantkit sync pull` | Download grants/responses from Supabase to local markdown |
| `grantkit sync push` | Upload local changes to Supabase |
| `grantkit sync watch` | Auto-sync on file changes |
| `grantkit validate` | Check NSF compliance |
| `grantkit check-salaries` | Validate salaries against OEWS data |
| `grantkit budget` | Generate budget narrative and calculations |
| `grantkit pdf` | Generate NSF-compliant PDF |

## Features

| Feature | Description |
|---------|-------------|
| **Supabase Sync** | Pull/push grants as local markdown with YAML frontmatter |
| **NSF Validation** | Check formatting, page limits, URLs, citations against PAPPG |
| **Salary Validation** | Compare salaries to BLS OEWS percentiles by occupation and metro area |
| **Budget Management** | GSA per diem lookups, indirect cost calculations |
| **PDF Generation** | NSF-compliant PDFs with proper fonts, margins, spacing |
| **Citation Management** | BibTeX integration with automatic bibliography |

## Links

- [GitHub Repository](https://github.com/GrantKit/grantkit)
- [Landing Page](https://grantkit.io)
- [Issue Tracker](https://github.com/GrantKit/grantkit/issues)

---

Created by [PolicyEngine](https://policyengine.org)

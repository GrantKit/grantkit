# GrantKit

[![CI](https://github.com/GrantKit/grantkit/actions/workflows/ci.yml/badge.svg)](https://github.com/GrantKit/grantkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Professional tools for grant proposal assembly, validation, and AI-assisted writing.**

GrantKit is an open-source CLI designed for **AI-native teams** who use AI coding agents (Claude Code, Cursor) and want the same workflow for grant writing.

## Why GrantKit?

Other grant tools have their own AI built in. But you already have Claude Code. GrantKit gets out of the way and lets your tools do the writing.

- **Supabase Sync** - Pull grants to local markdown, edit with AI, push back
- **Pre-submission validation** - Catch NSF PAPPG compliance issues before you submit
- **Salary validation** - Check personnel costs against BLS OEWS market data
- **Travel per diem** - Automatic GSA rate lookups by city and fiscal year
- **Open source** - Inspect, modify, and extend to your needs

## Quick Start

```bash
pip install grantkit

# Set up Supabase connection
export GRANTKIT_SUPABASE_URL="https://your-project.supabase.co"
export GRANTKIT_SUPABASE_KEY="your-key"

# Pull grants to local markdown
grantkit sync pull

# Edit with your favorite AI tool
claude "improve the broader impacts section"

# Validate and push changes
grantkit validate
grantkit sync push
```

## How It Works

GrantKit syncs between local files and the cloud. Use AI tools locally, collaborate in the browser.

```
┌─────────────────┐     grantkit sync pull     ┌─────────────────┐
│                 │ ◄──────────────────────────│                 │
│   Local Files   │                            │    Supabase     │
│   (Markdown)    │ ──────────────────────────►│    (Cloud)      │
│                 │     grantkit sync push     │                 │
└─────────────────┘                            └─────────────────┘
        │
        │  Edit with Claude Code,
        │  Cursor, or any AI tool
        ▼
```

### Local File Structure

```
my-grants/
├── nsf-cssi/
│   ├── grant.yaml
│   └── responses/
│       ├── abstract.md
│       ├── broader_impacts.md
│       └── technical_approach.md
├── arnold-labor/
│   └── ...
```

### Response Format

```markdown
---
title: Broader Impacts
key: broader_impacts
word_limit: 2500
status: draft
---

# Broader Impacts

PolicyEngine democratizes policy analysis...
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `grantkit sync pull` | Download grants from Supabase to local markdown |
| `grantkit sync push` | Upload local changes to Supabase |
| `grantkit sync watch` | Auto-sync on file changes |
| `grantkit validate` | Check NSF compliance |
| `grantkit check-salaries` | Validate salaries against BLS OEWS data |
| `grantkit budget` | Generate budget narrative and calculations |
| `grantkit pdf` | Generate NSF-compliant PDF |

## Salary Validation

Compare proposed salaries to BLS market data:

```bash
# Check a single salary
grantkit check-salaries --salary 150000 --occupation software_developer

# Check with geographic adjustment
grantkit check-salaries --salary 180000 --occupation software_developer --area san_francisco

# Validate all personnel from budget
grantkit check-salaries --from-budget
```

Supported occupations: `software_developer`, `data_scientist`, `cs_professor`, `economist`, `postdoc`, `statistician`, and more.

## NSF Validation

```bash
grantkit validate
```

Checks:
- Page limits (Project Summary, Description, Bio Sketches)
- Font size and margin requirements
- URL restrictions in project description
- Required sections present
- Citation completeness

## Installation Options

```bash
# Core CLI
pip install grantkit

# With PDF generation
pip install grantkit[pdf]

# All features
pip install grantkit[all]
```

## Documentation

Full documentation at [docs.grantkit.io](https://docs.grantkit.io)

- [Getting Started](https://docs.grantkit.io/getting-started)
- [CLI Reference](https://docs.grantkit.io/cli/overview)
- [Salary Validation](https://docs.grantkit.io/features/salary-validation)
- [API Reference](https://docs.grantkit.io/api-reference)

## Development

```bash
git clone https://github.com/GrantKit/grantkit.git
cd grantkit
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black . && ruff check --fix .
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [Website](https://grantkit.io)
- [Documentation](https://docs.grantkit.io)
- [GitHub](https://github.com/GrantKit/grantkit)
- [Issues](https://github.com/GrantKit/grantkit/issues)

Created by [PolicyEngine](https://policyengine.org)

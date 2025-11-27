# GrantKit

[![CI](https://github.com/GrantKit/grantkit/actions/workflows/ci.yml/badge.svg)](https://github.com/GrantKit/grantkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

**Grant writing for the AI agent era.**

GrantKit syncs your grants between a cloud database and local markdown files—so AI coding agents can edit them like code.

## The Paradigm

> "2023 was the year of the chatbot. 2024 was the year of RAG and finetuning. 2025 has been the year of MCP and tool use. **2026 will be the year of the computer environment and filesystem.**"
>
> — [Alex Albert, Anthropic](https://x.com/alexalbert__/status/1983209299624243529)

AI agents like Claude Code, Cursor, Gemini CLI, and Codex are transforming how we write code. They read files, understand context, make surgical edits, and commit changes—all with full git history and diff review.

**But most grant tools trap your content in web UIs where AI can't help.**

GrantKit bridges this gap:
- Your grants live in **Supabase** for team collaboration and web access
- You edit them as **local markdown files** where AI agents excel
- Changes sync bidirectionally with conflict detection

## Why Files, Not Apps?

Other grant tools have their own AI built in. But you already have Claude Code. GrantKit gets out of the way and lets your tools do the writing.

When your grants are files:
- **AI agents can read the full context** (not just what fits in an API response)
- **Changes are reviewable diffs** (not opaque database mutations)
- **Git provides history and rollback** (not "undo" buttons with limited memory)
- **You control the AI** (use Claude, GPT-4, Gemini, local models—whatever works)

## Features

- **Supabase Sync** - Pull grants to local markdown, edit with AI, push back
- **OAuth Device Flow** - Secure CLI authentication via browser (no API keys)
- **Pre-submission validation** - Catch NSF PAPPG compliance issues before you submit
- **Salary validation** - Check personnel costs against BLS OEWS market data
- **Travel per diem** - Automatic GSA rate lookups by city and fiscal year
- **Open source** - Inspect, modify, and extend to your needs

## Quick Start

```bash
pip install grantkit

# Authenticate via browser (OAuth device flow)
grantkit auth login

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
| `grantkit auth login` | Authenticate via browser (OAuth device flow) |
| `grantkit auth whoami` | Show currently logged-in user |
| `grantkit auth logout` | Clear stored credentials |
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

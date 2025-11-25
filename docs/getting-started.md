# Getting Started

This guide walks you through installing GrantKit and syncing your first grant proposal.

## Installation

```bash
pip install grantkit
```

## Prerequisites

- Python 3.10 or higher
- A Supabase project with grants data (or use GrantKit's hosted instance)

## Quick Start

### 1. Set up your Supabase connection

```bash
export GRANTKIT_SUPABASE_URL="https://your-project.supabase.co"
export GRANTKIT_SUPABASE_KEY="your-anon-key"
```

Or create a `.grantkit.yaml` config file:

```yaml
supabase:
  url: https://your-project.supabase.co
  key: your-anon-key
```

### 2. Pull grants to local files

```bash
grantkit sync pull
```

This creates a directory structure like:

```
my-grants/
├── nsf-cssi/
│   ├── grant.yaml
│   └── responses/
│       ├── abstract.md
│       ├── broader_impacts.md
│       └── technical_approach.md
├── arnold-foundation/
│   └── ...
```

### 3. Edit with AI tools

Open the project in your editor and use Claude Code, Cursor, or any AI tool:

```bash
claude "improve the broader impacts section to emphasize open source benefits"
```

### 4. Validate your proposal

```bash
grantkit validate
```

This checks NSF compliance rules like page limits, formatting requirements, and prohibited content.

### 5. Push changes back

```bash
grantkit sync push
```

Or watch for changes and auto-sync:

```bash
grantkit sync watch
```

## Response File Format

Each response is a markdown file with YAML frontmatter:

```markdown
---
title: Broader Impacts
key: broader_impacts
word_limit: 2500
status: draft
---

# Broader Impacts

PolicyEngine democratizes policy analysis by providing free,
open-source tools that enable researchers, journalists, and
policymakers to understand the effects of tax and benefit reforms.
```

## Next Steps

- [CLI Reference](cli/overview.md) - Full command documentation
- [Salary Validation](features/salary-validation.md) - Check salaries against BLS data
- [NSF Validation](cli/validation.md) - Compliance checking details

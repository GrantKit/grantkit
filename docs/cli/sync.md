# Sync Commands

The `sync` commands synchronize grant data between Supabase and local markdown files.

## Configuration

Set environment variables:

```bash
export GRANTKIT_SUPABASE_URL="https://your-project.supabase.co"
export GRANTKIT_SUPABASE_KEY="your-anon-key"
```

Or create `.grantkit.yaml`:

```yaml
supabase:
  url: https://your-project.supabase.co
  key: your-anon-key
```

## Commands

### `grantkit sync pull`

Download grants and responses from Supabase to local files.

```bash
grantkit sync pull
```

Creates directory structure:

```
grants/
├── {grant-slug}/
│   ├── grant.yaml          # Grant metadata
│   └── responses/
│       ├── {response-key}.md
│       └── ...
```

**grant.yaml example:**

```yaml
id: abc123
name: NSF CSSI 2025
foundation: NSF
program: CSSI
amount_requested: 600000
duration_years: 3
deadline: "2025-02-15"
status: draft
```

**Response markdown example:**

```markdown
---
id: resp123
title: Project Summary
key: project_summary
word_limit: 1500
char_limit: null
status: draft
---

# Project Summary

Your response content here...
```

### `grantkit sync push`

Upload local file changes to Supabase.

```bash
grantkit sync push
```

Reads local markdown files and updates corresponding Supabase records. Only modified content is synced.

### `grantkit sync watch`

Watch for file changes and automatically sync to Supabase.

```bash
grantkit sync watch
```

Monitors the grants directory and pushes changes on save. Useful when editing with AI tools that make frequent updates.

## Workflow

The recommended workflow for AI-assisted editing:

```bash
# 1. Pull latest from cloud
grantkit sync pull

# 2. Start watch mode in background
grantkit sync watch &

# 3. Edit with AI tools
claude "expand the methodology section with more technical details"

# 4. Changes auto-sync as you work
# Or manually push when done
grantkit sync push
```

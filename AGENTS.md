# Repository Guidelines

## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Quick Start

```bash
bd ready                              # Check for ready work
bd create "Title" -t task -p 2        # Create issue
bd update bd-123 --status in_progress # Claim work
bd close bd-123 --reason "Done"       # Complete work
```

### Priority Levels

- **P0**: Critical (security, data loss, broken CI)
- **P1**: High (major features, important bugs)
- **P2**: Medium (default, nice-to-have)
- **P3**: Low (polish, optimization)
- **P4**: Backlog (future ideas)

### Issue Types

- `epic` - Large initiative with subtasks
- `feature` - New functionality
- `task` - General work item
- `bug` - Something broken
- `chore` - Maintenance (deps, tooling)

### Dependency Types

Use `--deps <type>:<id>` when creating issues:

```bash
# Subtask under an epic
bd create "Add OAuth refresh" -p 1 --deps parent-child:bd-xxx

# Found new work while working on another issue
bd create "Found sync bug" -p 1 --deps discovered-from:bd-abc

# This issue blocks another
bd create "Fix auth first" -p 1 --deps blocks:bd-xyz
```

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   ```bash
   bd create "Found issue" -p 1 --deps discovered-from:<current-task-id>
   ```
5. **Complete**: `bd close <id> --reason "Brief summary"`
6. **Commit together**: Always commit `.beads/issues.jsonl` with code changes

### Important Rules

- Use bd for ALL task tracking
- Always include descriptions with `--description="..."` for context
- Check `bd ready` before asking "what should I work on?"
- Do NOT create markdown TODO lists
- Link discovered work with `discovered-from` to maintain context

---

## Project Overview

**GrantKit** - Grant writing for the AI agent era. Syncs grants between Supabase (cloud) and local markdown files so AI coding agents can edit them like code.

### Architecture

```
grantkit/
├── __init__.py      # Package init, version
├── cli.py           # Click CLI commands (main entry point)
├── auth.py          # OAuth device flow authentication
├── sync.py          # Supabase <-> local file sync
├── ai/              # AI integrations (Anthropic, OpenAI)
├── budget/          # Budget calculation and narrative
├── core/            # Core data models and logic
├── data/            # Static data files (YAML configs)
├── funders/         # Funder-specific rules (NSF, etc.)
├── pdf/             # PDF generation (WeasyPrint)
├── references/      # Citation and bibliography handling
├── templates/       # Jinja2 templates
├── utils/           # Shared utilities
└── validators/      # NSF PAPPG compliance checks
```

---

## Build, Test, and Development Commands

```bash
# Setup
pip install -e ".[dev]"

# Run tests
pytest                           # All tests
pytest tests/test_cli.py -v      # Single file
pytest -k "test_sync"            # By name pattern
pytest --cov=grantkit            # With coverage

# Format and lint
black .                          # Format
ruff check --fix .               # Lint + autofix
mypy grantkit/                   # Type check

# Pre-commit (all checks)
black . && ruff check --fix . && pytest
```

### CI Workflow

Push triggers:
1. `black --check .`
2. `ruff check .`
3. `pytest`

---

## Code Style & Conventions

- **Python**: 3.12+, strict typing encouraged
- **Line length**: 79 chars (black + ruff configured)
- **Imports**: sorted by ruff (isort rules)
- **Naming**:
  - `snake_case` for functions, variables, modules
  - `PascalCase` for classes
  - `UPPER_SNAKE` for constants
- **CLI**: Click with rich for output formatting
- **Testing**: pytest, fixtures in `conftest.py`

### Key Patterns

- **Sync operations**: Always handle conflicts explicitly
- **Auth**: OAuth device flow, tokens stored via keyring
- **Validation**: Return list of `ValidationError` objects
- **CLI output**: Use `rich.console` for formatted output

---

## Testing Guidelines

- Co-locate tests in `tests/` directory
- Use pytest fixtures for common setup
- Mock Supabase calls in sync tests
- Test CLI commands via Click's `CliRunner`

```python
# Example CLI test
from click.testing import CliRunner
from grantkit.cli import main

def test_validate_command():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", "--help"])
    assert result.exit_code == 0
```

---

## Commit & PR Guidelines

- Commits: Imperative mood ("Add sync command", "Fix OAuth flow")
- Always run `black . && ruff check --fix . && pytest` before committing
- Include `.beads/issues.jsonl` in commits when issues change
- PR descriptions: Summary, test plan, link to bd issue

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `GRANTKIT_AUTH_TOKEN` | OAuth access token (auto-managed) |
| `BLS_API_KEY` | Optional: BLS API for salary data |

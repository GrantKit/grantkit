# CLI Overview

GrantKit provides a command-line interface for managing grant proposals.

## Global Options

```bash
grantkit [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Enable verbose logging |
| `--project-root DIRECTORY` | Project root directory (auto-detected if not specified) |
| `--help` | Show help message |

## Commands

### Sync Commands

| Command | Description |
|---------|-------------|
| `sync pull` | Download grants from Supabase to local markdown files |
| `sync push` | Upload local changes to Supabase |
| `sync watch` | Watch for file changes and auto-sync |

### Validation Commands

| Command | Description |
|---------|-------------|
| `validate` | Run NSF compliance validation |
| `check-salaries` | Validate salaries against BLS OEWS data |
| `check-citations` | Check bibliography completeness |
| `check-pages` | Quick page count check |
| `validate-urls` | Validate URLs and email addresses |

### Build Commands

| Command | Description |
|---------|-------------|
| `build` | Assemble complete proposal from sections |
| `budget` | Build and validate project budget |
| `pdf` | Generate NSF-compliant PDF |
| `export` | Export to DOCX or PDF format |

### Utility Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize new proposal project |
| `status` | Show proposal completion status |
| `programs` | List available NSF program configs |
| `pdf-capabilities` | Check PDF generation dependencies |

## Examples

```bash
# Pull all grants
grantkit sync pull

# Validate with strict mode (warnings are errors)
grantkit validate --strict

# Check if a salary is reasonable
grantkit check-salaries --salary 150000 --occupation software_developer

# Generate PDF
grantkit pdf --output proposal.pdf
```

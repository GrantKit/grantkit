# GrantKit

Professional tools for grant proposal assembly, validation, and AI-assisted writing.

## Features

- **Multi-funder support**: NSF, Arnold Ventures, and more
- **Proposal assembly**: Combine sections into complete proposals
- **NSF compliance validation**: Check formatting, page limits, and content rules
- **Budget management**: Calculate and validate budgets against program caps
- **PDF generation**: Generate NSF-compliant PDFs with proper formatting
- **Citation management**: BibTeX integration with automatic bibliography generation
- **AI assistance** (coming soon): Review simulation, success probability estimation

## Installation

```bash
pip install grantkit
```

For PDF generation:
```bash
pip install grantkit[pdf]
```

For all features including AI:
```bash
pip install grantkit[all]
```

## Quick Start

### Initialize a new proposal

```bash
grantkit init cssi
```

This creates a project structure with templates for the CSSI program.

### Check proposal status

```bash
grantkit status
```

### Build the proposal

```bash
grantkit build
```

### Validate NSF compliance

```bash
grantkit validate
```

### Generate PDF

```bash
grantkit pdf --optimize
```

## Supported Programs

| Program | Description | Budget Cap |
|---------|-------------|------------|
| `cssi` | Cyberinfrastructure for Sustained Scientific Innovation | $5M |
| `pose-phase-2` | Pathways to Enable Open-Source Ecosystems | $1.5M |
| `career` | Faculty Early Career Development | $500K |

List all programs:
```bash
grantkit programs
```

## Project Structure

GrantKit expects this structure in your project:

```
your-proposal/
  grant.yaml           # Main configuration
  docs/
    responses/
      project_summary.md
      project_description.md
      ...
  budget/
    budget.yaml
  docs/
    references.bib     # Optional BibTeX file
```

## Configuration

Create a `grant.yaml` file:

```yaml
title: "Your Project Title"
pi: "Principal Investigator Name"
institution: "Your Institution"

nsf:
  program_id: cssi-elements
  sections:
    - id: project_summary
      title: "Project Summary"
      file: docs/responses/project_summary.md
      required: true
    - id: project_description
      title: "Project Description"
      file: docs/responses/project_description.md
      required: true
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `grantkit init <program>` | Initialize new proposal project |
| `grantkit build` | Assemble proposal from sections |
| `grantkit validate` | Run NSF compliance checks |
| `grantkit status` | Show completion status |
| `grantkit budget` | Build and validate budget |
| `grantkit pdf` | Generate NSF-compliant PDF |
| `grantkit programs` | List available programs |
| `grantkit check-citations` | Verify bibliography completeness |

## Development

```bash
git clone https://github.com/grantkit/grantkit.git
cd grantkit
pip install -e ".[dev]"
```

Run tests:
```bash
pytest
```

Format code:
```bash
black .
ruff check --fix .
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

Created by [PolicyEngine](https://policyengine.org).

# Sample NSF Grant

This is a sample NSF CSSI Elements grant project demonstrating GrantKit's structure and features.

## Structure

```
sample-nsf-grant/
├── grant.yaml           # Project configuration
├── budget.yaml          # Budget specification
├── README.md            # This file
└── responses/
    ├── project_summary.md
    ├── project_description.md
    ├── broader_impacts.md
    └── references.md
```

## Usage

### Validate the proposal

```bash
cd examples/sample-nsf-grant
grantkit validate
```

### Check budget

```bash
grantkit budget
```

### Check salaries against market data

```bash
grantkit check-salaries --from-budget
```

### Assemble complete proposal

```bash
grantkit build
```

### Generate PDF

```bash
grantkit pdf --output proposal.pdf
```

## Notes

- This is a fictional example for demonstration purposes
- Amounts and names are illustrative only
- See the main GrantKit documentation for full usage instructions

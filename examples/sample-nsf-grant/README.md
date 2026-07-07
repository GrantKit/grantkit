# Sample NSF grant

A fictional NSF CSSI Elements grant that showcases the unified 0.2.0 schema and
the `nsf-pappg` rule pack.

## Structure

```
sample-nsf-grant/
├── grant.yaml           # unified schema: funder, program, pack, sections
├── budget.yaml          # budget specification
├── README.md            # this file
└── responses/
    ├── project_summary.md
    ├── project_description.md
    ├── broader_impacts.md
    └── references.md
```

## Usage

```bash
cd examples/sample-nsf-grant

# Lint against the NSF PAPPG rules
grantkit check

# Completion, word counts, deadline countdown
grantkit status

# Compile the proposal and a shareable review page
grantkit build --share

# Emit a review packet for an AI agent
grantkit review --pack
```

## Notes

- Fictional example for demonstration; amounts and names are illustrative only.
- `grant.yaml` sets `pack: nsf-pappg`, so `grantkit check` runs the full NSF
  PAPPG content engine (prohibited URLs/emails, required Overview /
  Intellectual Merit / Broader Impacts statements).
- See the main GrantKit documentation for full usage.

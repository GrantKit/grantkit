# Validation Commands

GrantKit includes comprehensive validation for NSF compliance and proposal quality.

## NSF Compliance Validation

```bash
grantkit validate [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--strict` | Treat warnings as errors |
| `-o, --output PATH` | Save validation report to file |

### What's Checked

**Page Limits:**
- Project Summary: 1 page
- Project Description: 15 pages
- References Cited: no limit
- Biographical Sketches: 3 pages per person
- Budget Justification: 5 pages

**Formatting Rules:**
- Minimum font size (11pt for body, 10pt for figures)
- Margin requirements (1 inch)
- Line spacing requirements

**Content Rules:**
- No URLs in project description (with exceptions)
- Required sections present
- Proper citation format

### Example Output

```
$ grantkit validate

NSF Compliance Validation
=========================

[PASS] Page limits
  - Project Summary: 1/1 pages
  - Project Description: 12/15 pages

[WARN] URLs found in Project Description
  - Line 234: https://example.com
  - Consider removing or citing as reference

[PASS] Required sections present
[PASS] Font size requirements
[PASS] Margin requirements

Summary: 4 passed, 1 warning, 0 errors
```

## Salary Validation

```bash
grantkit check-salaries [OPTIONS]
```

Compares proposed salaries to BLS OEWS (Occupational Employment and Wage Statistics) data.

### Options

| Option | Description |
|--------|-------------|
| `-o, --occupation TEXT` | Occupation code or name |
| `-s, --salary FLOAT` | Annual salary to validate |
| `-m, --months FLOAT` | Number of months (for annualization) |
| `-a, --area TEXT` | Geographic area |
| `--from-budget` | Validate all personnel from budget.yaml |

### Examples

```bash
# Check a single salary
grantkit check-salaries --salary 150000 --occupation software_developer

# Check PI salary (3 months = $45k, annualized = $180k)
grantkit check-salaries --salary 45000 --months 3 --occupation cs_professor

# Validate all budget personnel
grantkit check-salaries --from-budget --area san_francisco
```

See [Salary Validation](../features/salary-validation.md) for full documentation.

## Citation Validation

```bash
grantkit check-citations
```

Checks that all citations in the proposal are present in the bibliography and vice versa.

## URL Validation

```bash
grantkit validate-urls
```

Validates URLs and email addresses for NSF compliance. NSF generally prohibits URLs in the project description.

## Page Count

```bash
grantkit check-pages
```

Quick check of page counts for generated PDFs against NSF limits.

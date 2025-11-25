# Budget Commands

The `budget` command builds and validates project budgets with NSF-compliant calculations.

## Usage

```bash
grantkit budget [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-o, --output-dir PATH` | Output directory for budget files |
| `--format [markdown\|json\|both]` | Output format (default: both) |

## Budget Configuration

Create a `budget.yaml` file in your project:

```yaml
project:
  title: "PolicyEngine Infrastructure"
  duration_years: 3
  start_date: "2025-09-01"

personnel:
  - name: "Dr. Jane Smith"
    role: "PI"
    base_salary: 180000
    months_per_year: 2
    fringe_rate: 0.32

  - name: "Software Developer"
    role: "Senior Personnel"
    base_salary: 140000
    months_per_year: 12
    fringe_rate: 0.32

travel:
  - description: "Annual conference attendance"
    destination: "Washington, DC"
    travelers: 2
    days: 4
    per_year: 1

equipment:
  - description: "Cloud computing credits"
    cost: 15000
    per_year: true

indirect:
  rate: 0.55
  base: "mtdc"  # Modified Total Direct Costs
```

## Output

Running `grantkit budget` generates:

**budget_summary.md:**

```markdown
# Budget Summary

## Year 1

| Category | Amount |
|----------|--------|
| Personnel | $185,600 |
| Fringe Benefits | $59,392 |
| Travel | $3,200 |
| Equipment | $15,000 |
| **Direct Costs** | **$263,192** |
| Indirect (55% MTDC) | $136,556 |
| **Year 1 Total** | **$399,748** |
```

**budget.json:**

```json
{
  "years": [
    {
      "year": 1,
      "personnel": 185600,
      "fringe": 59392,
      "travel": 3200,
      "equipment": 15000,
      "direct_total": 263192,
      "indirect": 136556,
      "total": 399748
    }
  ],
  "grand_total": 1199244
}
```

## Travel Per Diem

GrantKit automatically looks up GSA per diem rates for travel calculations:

```yaml
travel:
  - destination: "San Francisco, CA"
    days: 3
    # Per diem auto-calculated from GSA rates
```

See [Travel Per Diem](../features/travel-per-diem.md) for details.

## Salary Validation

Use `check-salaries` to validate personnel costs against BLS market data:

```bash
grantkit check-salaries --from-budget
```

See [Salary Validation](../features/salary-validation.md) for details.

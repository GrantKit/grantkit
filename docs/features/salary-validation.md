# Salary Validation

GrantKit validates proposed salaries against Bureau of Labor Statistics (BLS) Occupational Employment and Wage Statistics (OEWS) data to ensure they're reasonable and defensible.

## Why Validate Salaries?

NSF and other funders scrutinize personnel costs. Salaries significantly above market rates may:

- Delay award while questions are resolved
- Require budget modifications
- Raise red flags for reviewers

GrantKit compares your proposed salaries to national and regional wage percentiles, flagging potential issues before submission.

## Usage

### Single Salary Check

```bash
grantkit check-salaries --salary 150000 --occupation software_developer
```

Output:

```
Salary Validation: Software Developer
=====================================
Proposed: $150,000/year
Area: National

OEWS Wage Distribution:
  10th percentile: $70,210
  25th percentile: $92,450
  50th percentile: $120,730
  75th percentile: $151,960
  90th percentile: $168,570

Your salary: 74th percentile

Status: OK
The proposed salary is within normal range.
```

### With Geographic Area

```bash
grantkit check-salaries --salary 180000 --occupation software_developer --area san_francisco
```

San Francisco wages are higher than national averages, so the same salary may be at a different percentile.

### Annualized Salaries

For partial-year appointments (common for PIs):

```bash
# PI at $45,000 for 3 months = $180,000 annualized
grantkit check-salaries --salary 45000 --months 3 --occupation cs_professor
```

### From Budget File

Validate all personnel in your budget:

```bash
grantkit check-salaries --from-budget
```

## Supported Occupations

| Name | SOC Code | Description |
|------|----------|-------------|
| `software_developer` | 15-1252 | Software Developers |
| `data_scientist` | 15-2051 | Data Scientists |
| `cs_professor` | 25-1021 | Computer Science Teachers, Postsecondary |
| `economist` | 19-3011 | Economists |
| `postdoc` | 19-4099 | Life, Physical, Social Science Technicians |
| `research_assistant` | 19-4061 | Social Science Research Assistants |
| `statistician` | 15-2041 | Statisticians |
| `operations_research` | 15-2031 | Operations Research Analysts |

You can also use SOC codes directly: `--occupation 15-1252`

## Supported Areas

| Name | Code | Description |
|------|------|-------------|
| `national` | 0000000 | National average |
| `san_francisco` | 41860 | San Francisco-Oakland-Hayward, CA |
| `boston` | 14460 | Boston-Cambridge-Nashua, MA-NH |
| `washington_dc` | 47900 | Washington-Arlington-Alexandria, DC-VA-MD-WV |
| `new_york` | 35620 | New York-Newark-Jersey City, NY-NJ-PA |
| `los_angeles` | 31080 | Los Angeles-Long Beach-Anaheim, CA |
| `seattle` | 42660 | Seattle-Tacoma-Bellevue, WA |
| `austin` | 12420 | Austin-Round Rock, TX |

## Thresholds

| Percentile | Status |
|------------|--------|
| < 10th | Warning: unusually low |
| 10th - 75th | OK |
| 75th - 95th | Warning: above market median |
| > 95th | Error: requires justification |

## Programmatic Usage

```python
from grantkit.budget import SalaryValidator, get_salary_validator

validator = get_salary_validator(default_area="san_francisco")

result = validator.validate_salary(
    salary=150000,
    occupation="software_developer",
    months=12,
)

print(f"Percentile: {result.percentile}")
print(f"Valid: {result.is_valid}")
print(f"Warnings: {result.warnings}")
```

## Data Source

Wage data comes from the BLS Occupational Employment and Wage Statistics (OEWS) program:

- Updated annually (May reference period)
- Covers 800+ occupations
- Available for national, state, and metro areas
- https://www.bls.gov/oes/

GrantKit caches OEWS data locally to avoid repeated API calls. Use a BLS API key for higher rate limits:

```bash
export BLS_API_KEY="your-key-here"
```

Register for a free key at https://www.bls.gov/developers/

# Salary Validation

GrantKit validates proposed salaries against Bureau of Labor Statistics (BLS) Occupational Employment and Wage Statistics (OEWS) data to ensure they're reasonable and defensible.

## Why Validate Salaries?

NSF and other funders scrutinize personnel costs. Salaries significantly above market rates may:

- Delay award while questions are resolved
- Require budget modifications
- Raise red flags for reviewers

GrantKit compares your proposed salaries to national and regional wage percentiles, flagging potential issues before submission.

## How it runs

Salary validation runs as part of `grantkit check` — but only when a
`BLS_API_KEY` is set in the environment, because it makes network calls to the
BLS API. Without a key, `check` skips it entirely and stays offline.

```bash
export BLS_API_KEY="your-key-here"   # https://www.bls.gov/developers/
grantkit check
```

Personnel are read from your `budget.yaml` (`personnel.senior_key`). Each
person may carry an `occupation` (a SOC code or a supported name), `months`,
and `area`; GrantKit annualizes the salary and estimates its OEWS percentile.
Findings surface as check items:

- `salary_above_market` (error) — above the 95th percentile.
- `salary_market_check` (warning) — above the 75th or below the 10th.

For ad-hoc checks outside a grant, use the programmatic API below.

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

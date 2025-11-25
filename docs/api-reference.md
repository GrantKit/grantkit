# API Reference

GrantKit can be used programmatically in Python applications.

## Installation

```bash
pip install grantkit
```

## Sync Client

Sync grants between Supabase and local files.

```python
from grantkit.sync import get_sync_client, SyncConfig

# From environment variables
client = get_sync_client()

# Or explicit configuration
config = SyncConfig(
    supabase_url="https://your-project.supabase.co",
    supabase_key="your-anon-key",
)
client = get_sync_client(config)

# Pull grants to local directory
client.pull(output_dir="./grants")

# Push local changes
client.push(input_dir="./grants")
```

## Salary Validation

Validate salaries against BLS OEWS data.

```python
from grantkit.budget import (
    SalaryValidator,
    get_salary_validator,
    ACADEMIC_OCCUPATION_CODES,
    METRO_AREA_CODES,
)

# Create validator
validator = get_salary_validator(
    default_area="san_francisco",
    bls_api_key="optional-key",
)

# Validate a single salary
result = validator.validate_salary(
    salary=150000,
    occupation="software_developer",
    months=12,
    area="national",
)

print(f"Percentile: {result.percentile}")
print(f"Valid: {result.is_valid}")
print(f"Warnings: {result.warnings}")
print(f"Issues: {result.issues}")

# Validate budget personnel
personnel = [
    {"description": "PI (3 months)", "amount": 45000, "months": 3},
    {"description": "Software Developer", "amount": 140000},
]

results = validator.validate_budget_personnel(personnel)
for r in results:
    print(f"{r.role}: {r.percentile}th percentile")
```

### SalaryValidationResult

```python
@dataclass
class SalaryValidationResult:
    salary: float           # Annualized salary
    occupation: str         # Occupation code
    area: str              # Geographic area
    percentile: float      # Estimated percentile (0-99)
    is_valid: bool         # True if no errors
    warnings: list[str]    # Warning messages
    issues: list[str]      # Error messages
    wage_data: WageData    # Raw OEWS data
```

### Occupation Codes

```python
ACADEMIC_OCCUPATION_CODES = {
    "software_developer": "15-1252",
    "data_scientist": "15-2051",
    "cs_professor": "25-1021",
    "economist": "19-3011",
    "postdoc": "19-4099",
    "research_assistant": "19-4061",
    "statistician": "15-2041",
    "operations_research": "15-2031",
}
```

### Metro Area Codes

```python
METRO_AREA_CODES = {
    "national": "0000000",
    "san_francisco": "41860",
    "boston": "14460",
    "washington_dc": "47900",
    "new_york": "35620",
    "los_angeles": "31080",
    "seattle": "42660",
    "austin": "12420",
}
```

## Budget Manager

Build and validate project budgets.

```python
from grantkit.budget import BudgetManager

manager = BudgetManager(project_root="./my-proposal")

# Load budget configuration
budget = manager.load_budget()

# Calculate totals
summary = manager.calculate_summary()
print(f"Total direct costs: ${summary.direct_total:,}")
print(f"Total indirect: ${summary.indirect:,}")
print(f"Grand total: ${summary.grand_total:,}")

# Generate budget narrative
narrative = manager.generate_narrative()
```

## NSF Validator

Run compliance checks on proposals.

```python
from grantkit.validation import NSFValidator

validator = NSFValidator(project_root="./my-proposal")

# Run all checks
results = validator.validate()

for check in results:
    status = "PASS" if check.passed else "FAIL"
    print(f"[{status}] {check.name}: {check.message}")

# Check specific rules
page_results = validator.check_page_limits()
url_results = validator.check_urls()
citation_results = validator.check_citations()
```

## PDF Generator

Generate NSF-compliant PDFs.

```python
from grantkit.pdf import PDFGenerator

generator = PDFGenerator(project_root="./my-proposal")

# Generate PDF
generator.generate(output_path="proposal.pdf")

# Check page counts
pages = generator.count_pages()
print(f"Project Description: {pages['description']} pages")
```

## Configuration

GrantKit looks for configuration in:

1. `.grantkit.yaml` in current directory
2. `~/.grantkit/config.yaml`
3. Environment variables

```yaml
# .grantkit.yaml
supabase:
  url: https://your-project.supabase.co
  key: your-anon-key

defaults:
  area: san_francisco

bls:
  api_key: your-bls-key  # Optional, for higher rate limits
```

Environment variables:

```bash
GRANTKIT_SUPABASE_URL=https://...
GRANTKIT_SUPABASE_KEY=your-key
BLS_API_KEY=your-key
```

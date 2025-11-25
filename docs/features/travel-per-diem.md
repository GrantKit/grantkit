# Travel Per Diem

GrantKit automatically calculates travel costs using official GSA (General Services Administration) per diem rates.

## Why Use GSA Rates?

Federal grants require travel costs to follow GSA guidelines:

- **Lodging**: Maximum reimbursable hotel rates by location
- **M&IE**: Meals and Incidental Expenses daily allowance
- **First/Last Day**: 75% of M&IE rate

Using GSA rates ensures your budget is defensible and compliant.

## Configuration

In your `budget.yaml`:

```yaml
travel:
  - description: "Annual conference (AAAS)"
    destination: "Washington, DC"
    travelers: 2
    days: 4
    per_year: 1

  - description: "Collaborator visit"
    destination: "Boston, MA"
    travelers: 1
    days: 3
    per_year: 2

  - description: "NSF project meeting"
    destination: "Alexandria, VA"
    travelers: 3
    days: 2
    per_year: 1
```

## Automatic Rate Lookup

When you run `grantkit budget`, GrantKit:

1. Looks up GSA rates for each destination
2. Calculates lodging, M&IE, and first/last day adjustments
3. Adds standard airfare estimates based on distance
4. Produces itemized travel budget

## Example Output

```
Travel Budget - Year 1
======================

1. Annual conference (AAAS) - Washington, DC
   Travelers: 2, Days: 4

   Per person:
     Airfare (estimated): $450
     Lodging: 3 nights × $258 = $774
     M&IE: 2 full days × $79 = $158
     M&IE: 2 partial days × $59 = $118
     Subtotal: $1,500

   Total (2 travelers): $3,000

2. Collaborator visit - Boston, MA
   ...

Year 1 Travel Total: $8,450
```

## GSA Rate Sources

GrantKit fetches rates from:

- **CONUS**: https://www.gsa.gov/travel/plan-book/per-diem-rates
- **OCONUS**: https://aoprals.state.gov/web920/per_diem.asp

Rates are cached locally and updated when the fiscal year changes (October 1).

## Manual Override

You can specify custom rates if needed:

```yaml
travel:
  - description: "International conference"
    destination: "London, UK"
    travelers: 1
    days: 5
    lodging_rate: 350  # Override GSA
    mie_rate: 120
    airfare: 1200
```

## Fiscal Year

GSA rates change on October 1. GrantKit uses the appropriate fiscal year based on your project start date:

```yaml
project:
  start_date: "2025-09-01"  # Uses FY2025 rates
```

## Programmatic Usage

```python
from grantkit.budget import TravelCalculator

calc = TravelCalculator(fiscal_year=2025)

cost = calc.calculate_trip(
    destination="Washington, DC",
    days=4,
    travelers=2,
)

print(f"Lodging: ${cost.lodging}")
print(f"M&IE: ${cost.mie}")
print(f"Airfare: ${cost.airfare}")
print(f"Total: ${cost.total}")
```

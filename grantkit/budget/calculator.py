"""Budget auto-calculation from budget.yaml files.

Automatically calculates totals from line-item budgets and syncs
to grant.yaml to ensure consistency.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml


class BudgetCapError(Exception):
    """Raised when budget exceeds defined caps."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "Budget cap violations:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(message)


class BudgetCalculator:
    """Calculate budget totals from a budget.yaml file."""

    def __init__(self, budget_path: Path):
        """Initialize with path to budget.yaml.

        Args:
            budget_path: Path to budget.yaml file
        """
        self.budget_path = Path(budget_path)
        with open(self.budget_path, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f) or {}

        self.years = self.data.get("years_in_budget", 1)

    def calculate_senior_personnel(self) -> Dict[str, int]:
        """Calculate senior personnel totals per year.

        Returns:
            Dict with year_1, year_2, ..., year_N, and total keys
        """
        personnel = self.data.get("personnel", {})
        senior = personnel.get("senior_key", [])

        totals: Dict[str, int] = {}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            year_total = sum(person.get(year_key, 0) for person in senior)
            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_other_personnel(self) -> Dict[str, int]:
        """Calculate other personnel totals per year.

        Returns:
            Dict with year_1, year_2, ..., year_N, and total keys
        """
        personnel = self.data.get("personnel", {})
        other = personnel.get("other", [])

        totals: Dict[str, int] = {}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            year_total = sum(person.get(year_key, 0) for person in other)
            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_fringe_benefits(self) -> Dict[str, int]:
        """Calculate fringe benefits totals per year.

        If year_N is not specified but rate is, calculates fringe as rate * salaries.

        Returns:
            Dict with year_1, year_2, ..., year_N, total, and rate keys
        """
        fringe = self.data.get("fringe_benefits", {})
        rate = fringe.get("rate", 0)

        totals: Dict[str, Any] = {"rate": rate}
        grand_total = 0

        # Get salary totals for automatic calculation
        senior = self.calculate_senior_personnel()
        other = self.calculate_other_personnel()

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"

            if year_key in fringe:
                # Use explicit value if provided
                year_total = fringe[year_key]
            elif rate > 0:
                # Calculate from rate * salaries
                total_salary = senior[year_key] + other[year_key]
                year_total = int(total_salary * rate)
            else:
                year_total = 0

            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_equipment(self) -> Dict[str, int]:
        """Calculate equipment totals per year.

        Returns:
            Dict with year_1, year_2, ..., year_N, and total keys
        """
        equipment = self.data.get("equipment", [])

        totals: Dict[str, int] = {}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            year_total = sum(
                item.get(year_key, item.get("funds_per_year", 0))
                for item in equipment
            )
            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_travel(self) -> Dict[str, int]:
        """Calculate travel totals per year.

        Returns:
            Dict with year_1, year_2, ..., year_N, and total keys
        """
        travel = self.data.get("travel", {})
        domestic = travel.get("domestic", [])
        foreign = travel.get("foreign", [])

        totals: Dict[str, int] = {}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            year_total = 0

            # Domestic travel
            for item in domestic:
                if year_key in item:
                    year_total += item[year_key]
                elif "funds_per_year" in item:
                    year_total += item["funds_per_year"]

            # Foreign travel
            for item in foreign:
                if year_key in item:
                    year_total += item[year_key]
                elif "funds_per_year" in item:
                    year_total += item["funds_per_year"]

            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_participant_support(self) -> Dict[str, int]:
        """Calculate participant support totals per year.

        Returns:
            Dict with year_1, year_2, ..., year_N, and total keys
        """
        participant = self.data.get("participant_support", [])

        totals: Dict[str, int] = {}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            year_total = sum(
                item.get(year_key, item.get("funds_per_year", 0))
                for item in participant
            )
            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_other_direct_costs(self) -> Dict[str, int]:
        """Calculate other direct costs totals per year.

        Returns:
            Dict with year_1, year_2, ..., year_N, and total keys
        """
        other_dc = self.data.get("other_direct_costs", [])

        totals: Dict[str, int] = {}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            year_total = sum(
                item.get(year_key, item.get("funds_per_year", 0))
                for item in other_dc
            )
            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_total_direct_costs(self) -> Dict[str, int]:
        """Calculate total direct costs per year.

        Returns:
            Dict with year_1, year_2, ..., year_N, and total keys
        """
        senior = self.calculate_senior_personnel()
        other = self.calculate_other_personnel()
        fringe = self.calculate_fringe_benefits()
        equipment = self.calculate_equipment()
        travel = self.calculate_travel()
        participant = self.calculate_participant_support()
        other_dc = self.calculate_other_direct_costs()

        totals: Dict[str, int] = {}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            year_total = (
                senior[year_key]
                + other[year_key]
                + fringe[year_key]
                + equipment[year_key]
                + travel[year_key]
                + participant[year_key]
                + other_dc[year_key]
            )
            totals[year_key] = int(year_total)
            grand_total += year_total

        totals["total"] = int(grand_total)
        return totals

    def calculate_indirect_costs(self) -> Dict[str, Any]:
        """Calculate indirect costs based on MTDC.

        MTDC = total direct - equipment - participant support

        Returns:
            Dict with year_1, year_2, ..., year_N, total, and rate keys
        """
        indirect_spec = self.data.get("indirect_costs", {})
        rate = indirect_spec.get("rate", 0)

        direct = self.calculate_total_direct_costs()
        equipment = self.calculate_equipment()
        participant = self.calculate_participant_support()

        totals: Dict[str, Any] = {"rate": rate}
        grand_total = 0

        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            mtdc = (
                direct[year_key] - equipment[year_key] - participant[year_key]
            )
            indirect = int(mtdc * rate)
            totals[year_key] = indirect
            grand_total += indirect

        totals["total"] = int(grand_total)
        return totals

    def calculate_grand_total(self) -> int:
        """Calculate the grand total budget.

        Returns:
            Total budget as integer (dollars)
        """
        direct = self.calculate_total_direct_costs()
        indirect = self.calculate_indirect_costs()

        return int(direct["total"] + indirect["total"])

    def get_summary(self) -> Dict[str, Any]:
        """Get complete budget summary.

        Returns:
            Dict containing all budget components and totals
        """
        return {
            "senior_personnel": self.calculate_senior_personnel(),
            "other_personnel": self.calculate_other_personnel(),
            "fringe_benefits": self.calculate_fringe_benefits(),
            "equipment": self.calculate_equipment(),
            "travel": self.calculate_travel(),
            "participant_support": self.calculate_participant_support(),
            "other_direct_costs": self.calculate_other_direct_costs(),
            "total_direct_costs": self.calculate_total_direct_costs(),
            "indirect_costs": self.calculate_indirect_costs(),
            "grand_total": self.calculate_grand_total(),
        }

    def validate(self) -> List[str]:
        """Validate budget for consistency.

        Returns:
            List of warning messages for inconsistencies
        """
        warnings: List[str] = []

        # Validate fringe rate matches calculation
        fringe = self.data.get("fringe_benefits", {})
        fringe_rate = fringe.get("rate", 0)

        if fringe_rate > 0:
            senior = self.calculate_senior_personnel()
            other = self.calculate_other_personnel()

            for year in range(1, self.years + 1):
                year_key = f"year_{year}"
                total_salary = senior[year_key] + other[year_key]
                expected_fringe = int(total_salary * fringe_rate)
                actual_fringe = fringe.get(year_key, 0)

                if abs(expected_fringe - actual_fringe) > 1:
                    warnings.append(
                        f"Fringe mismatch {year_key}: expected ${expected_fringe:,} "
                        f"(rate {fringe_rate} * ${total_salary:,}), got ${actual_fringe:,}"
                    )

        # Validate indirect costs if summary exists
        summary = self.data.get("summary", {})
        indirect_spec = self.data.get("indirect_costs", {})
        indirect_rate = indirect_spec.get("rate", 0)

        if indirect_rate > 0 and summary:
            for year in range(1, self.years + 1):
                year_key = f"year_{year}"
                year_summary = summary.get(year_key, {})

                if "indirect" in year_summary:
                    actual_indirect = year_summary["indirect"]
                    calculated = self.calculate_indirect_costs()
                    expected_indirect = calculated[year_key]

                    if abs(expected_indirect - actual_indirect) > 1:
                        warnings.append(
                            f"Indirect mismatch {year_key}: expected ${expected_indirect:,}, "
                            f"got ${actual_indirect:,}"
                        )

        return warnings

    def calculate_yearly_totals(self) -> Dict[str, int]:
        """Calculate total budget (direct + indirect) for each year.

        Returns:
            Dict with year_1, year_2, ..., year_N keys and total amounts
        """
        direct = self.calculate_total_direct_costs()
        indirect = self.calculate_indirect_costs()

        totals: Dict[str, int] = {}
        for year in range(1, self.years + 1):
            year_key = f"year_{year}"
            totals[year_key] = direct[year_key] + indirect[year_key]

        return totals

    def validate_against_caps(self, grant_path: Path) -> List[str]:
        """Validate budget against caps defined in grant.yaml.

        Args:
            grant_path: Path to grant.yaml containing budget_cap and annual_budget_cap

        Returns:
            List of error messages for cap violations (empty if valid)
        """
        with open(grant_path, "r", encoding="utf-8") as f:
            grant_data = yaml.safe_load(f) or {}

        errors: List[str] = []

        budget_cap = grant_data.get("budget_cap")
        annual_cap = grant_data.get("annual_budget_cap")

        # Check total budget cap
        if budget_cap is not None:
            grand_total = self.calculate_grand_total()
            if grand_total > budget_cap:
                errors.append(
                    f"Total budget ${grand_total:,} exceeds total cap ${budget_cap:,} "
                    f"(over by ${grand_total - budget_cap:,})"
                )

        # Check annual budget caps
        if annual_cap is not None:
            yearly = self.calculate_yearly_totals()
            for year in range(1, self.years + 1):
                year_key = f"year_{year}"
                year_total = yearly[year_key]
                if year_total > annual_cap:
                    errors.append(
                        f"Year {year} budget ${year_total:,} exceeds annual cap "
                        f"${annual_cap:,} (over by ${year_total - annual_cap:,})"
                    )

        return errors


def calculate_budget_from_yaml(budget_path: Path) -> Dict[str, Any]:
    """Calculate budget summary from a budget.yaml file.

    Args:
        budget_path: Path to budget.yaml

    Returns:
        Budget summary dictionary
    """
    calc = BudgetCalculator(budget_path)
    return calc.get_summary()


def sync_budget_to_grant(budget_path: Path, grant_path: Path) -> None:
    """Sync calculated budget total to grant.yaml.

    Updates all budget-related fields in grant.yaml to match
    the calculated total from budget.yaml, including:
    - amount_requested (top level)
    - research_gov.total_requested (if present)

    Args:
        budget_path: Path to budget.yaml
        grant_path: Path to grant.yaml
    """
    calc = BudgetCalculator(budget_path)
    total = calc.calculate_grand_total()

    with open(grant_path, "r", encoding="utf-8") as f:
        grant_data = yaml.safe_load(f) or {}

    grant_data["amount_requested"] = total

    # Also update nested research_gov.total_requested if present
    if "research_gov" in grant_data and isinstance(
        grant_data["research_gov"], dict
    ):
        grant_data["research_gov"]["total_requested"] = total

    with open(grant_path, "w", encoding="utf-8") as f:
        yaml.dump(grant_data, f, default_flow_style=False, sort_keys=False)


def check_budget_caps(budget_path: Path, grant_path: Path) -> None:
    """Check budget against caps and raise if violated.

    Args:
        budget_path: Path to budget.yaml
        grant_path: Path to grant.yaml containing budget_cap and annual_budget_cap

    Raises:
        BudgetCapError: If budget exceeds any defined caps
    """
    calc = BudgetCalculator(budget_path)
    errors = calc.validate_against_caps(grant_path)

    if errors:
        raise BudgetCapError(errors)

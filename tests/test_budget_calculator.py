"""Tests for budget auto-calculation from budget.yaml."""

import tempfile
from pathlib import Path

import pytest
import yaml

from grantkit.budget.calculator import (
    BudgetCalculator,
    calculate_budget_from_yaml,
    sync_budget_to_grant,
)


class TestBudgetCalculator:
    """Tests for BudgetCalculator class."""

    @pytest.fixture
    def sample_budget_yaml(self) -> dict:
        """Sample budget.yaml in the format used by NSF grants."""
        return {
            "years_in_budget": 3,
            "personnel": {
                "senior_key": [
                    {
                        "name": "Max Ghenis",
                        "role": "PI",
                        "base_salary": 180000,
                        "year_1": 30000,
                        "year_2": 22500,
                        "year_3": 15000,
                    },
                    {
                        "name": "Nikhil Woodruff",
                        "role": "Co-PI",
                        "base_salary": 150000,
                        "year_1": 37500,
                        "year_2": 18750,
                        "year_3": 12500,
                    },
                ],
                "other": [
                    {
                        "category": "Other Professionals",
                        "title": "Research Software Engineer",
                        "base_salary": 140000,
                        "year_1": 70000,
                        "year_2": 77000,
                        "year_3": 77000,
                    }
                ],
            },
            "fringe_benefits": {
                "rate": 0.30,
                "year_1": 41250,
                "year_2": 35475,
                "year_3": 31350,
            },
            "equipment": [],
            "travel": {
                "domestic": [
                    {
                        "description": "NSF PI Meeting",
                        "funds_per_year": 2000,
                    },
                    {
                        "description": "Research conferences",
                        "funds_per_year": 2000,
                    },
                    {
                        "description": "R/Stata community",
                        "funds_per_year": 2000,
                    },
                ],
                "foreign": [],
            },
            "participant_support": [],
            "other_direct_costs": [
                {
                    "category": "Computer Services",
                    "description": "Cloud computing",
                    "funds_per_year": 12000,
                },
                {
                    "category": "Consultant Services",
                    "description": "TAXSIM validation consulting",
                    "funds_per_year": 5000,
                },
                {
                    "category": "Other",
                    "description": "Software licenses",
                    "funds_per_year": 3000,
                },
            ],
            "indirect_costs": {
                "rate": 0.10,
                "base": "mtdc",
            },
        }

    @pytest.fixture
    def budget_yaml_path(self, sample_budget_yaml) -> Path:
        """Create a temporary budget.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(sample_budget_yaml, f)
            return Path(f.name)

    def test_load_budget_yaml(self, budget_yaml_path):
        """Should load budget.yaml file."""
        calc = BudgetCalculator(budget_yaml_path)
        assert calc.data is not None
        assert calc.years == 3

    def test_calculate_senior_personnel_totals(self, budget_yaml_path):
        """Should calculate senior personnel totals per year."""
        calc = BudgetCalculator(budget_yaml_path)
        totals = calc.calculate_senior_personnel()

        assert totals["year_1"] == 67500  # 30000 + 37500
        assert totals["year_2"] == 41250  # 22500 + 18750
        assert totals["year_3"] == 27500  # 15000 + 12500
        assert totals["total"] == 136250

    def test_calculate_other_personnel_totals(self, budget_yaml_path):
        """Should calculate other personnel totals per year."""
        calc = BudgetCalculator(budget_yaml_path)
        totals = calc.calculate_other_personnel()

        assert totals["year_1"] == 70000
        assert totals["year_2"] == 77000
        assert totals["year_3"] == 77000
        assert totals["total"] == 224000

    def test_calculate_fringe_benefits(self, budget_yaml_path):
        """Should calculate fringe benefits totals."""
        calc = BudgetCalculator(budget_yaml_path)
        totals = calc.calculate_fringe_benefits()

        assert totals["year_1"] == 41250
        assert totals["year_2"] == 35475
        assert totals["year_3"] == 31350
        assert totals["total"] == 108075

    def test_calculate_travel(self, budget_yaml_path):
        """Should calculate travel totals."""
        calc = BudgetCalculator(budget_yaml_path)
        totals = calc.calculate_travel()

        # 3 items * 2000 each = 6000/year
        assert totals["year_1"] == 6000
        assert totals["year_2"] == 6000
        assert totals["year_3"] == 6000
        assert totals["total"] == 18000

    def test_calculate_other_direct_costs(self, budget_yaml_path):
        """Should calculate other direct costs totals."""
        calc = BudgetCalculator(budget_yaml_path)
        totals = calc.calculate_other_direct_costs()

        # 12000 + 5000 + 3000 = 20000/year
        assert totals["year_1"] == 20000
        assert totals["year_2"] == 20000
        assert totals["year_3"] == 20000
        assert totals["total"] == 60000

    def test_calculate_total_direct_costs(self, budget_yaml_path):
        """Should calculate total direct costs."""
        calc = BudgetCalculator(budget_yaml_path)
        totals = calc.calculate_total_direct_costs()

        # Year 1: 67500 + 70000 + 41250 + 0 + 6000 + 0 + 20000 = 204750
        assert totals["year_1"] == 204750
        assert (
            totals["year_2"] == 179725
        )  # 41250 + 77000 + 35475 + 6000 + 20000
        assert (
            totals["year_3"] == 161850
        )  # 27500 + 77000 + 31350 + 6000 + 20000

    def test_calculate_indirect_costs(self, budget_yaml_path):
        """Should calculate indirect costs based on MTDC."""
        calc = BudgetCalculator(budget_yaml_path)
        totals = calc.calculate_indirect_costs()

        # MTDC = total direct - equipment - participant support
        # Year 1: 204750 * 0.10 = 20475
        assert totals["year_1"] == 20475
        assert totals["rate"] == 0.10

    def test_calculate_grand_total(self, budget_yaml_path):
        """Should calculate grand total."""
        calc = BudgetCalculator(budget_yaml_path)
        total = calc.calculate_grand_total()

        # Should be sum of all years direct + indirect
        assert total > 0
        assert isinstance(total, (int, float))

    def test_get_summary(self, budget_yaml_path):
        """Should return complete budget summary."""
        calc = BudgetCalculator(budget_yaml_path)
        summary = calc.get_summary()

        assert "senior_personnel" in summary
        assert "other_personnel" in summary
        assert "fringe_benefits" in summary
        assert "travel" in summary
        assert "other_direct_costs" in summary
        assert "total_direct_costs" in summary
        assert "indirect_costs" in summary
        assert "grand_total" in summary

        # All totals should be integers (dollars)
        assert isinstance(summary["grand_total"], int)


class TestCalculateBudgetFromYaml:
    """Tests for the calculate_budget_from_yaml function."""

    def test_returns_calculated_total(self, tmp_path):
        """Should return calculated budget total."""
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 50000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.30, "year_1": 15000},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.10, "base": "mtdc"},
        }

        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        result = calculate_budget_from_yaml(budget_path)

        assert "grand_total" in result
        # 50000 + 15000 = 65000 direct, 6500 indirect = 71500
        assert result["grand_total"] == 71500


class TestSyncBudgetToGrant:
    """Tests for syncing calculated budget to grant.yaml."""

    def test_updates_grant_yaml_amount(self, tmp_path):
        """Should update amount_requested in grant.yaml."""
        # Create budget.yaml
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 100000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.30, "year_1": 30000},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.10, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        # Create grant.yaml with wrong amount
        grant_yaml = {
            "name": "Test Grant",
            "amount_requested": 999999,  # Wrong amount
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        # Sync
        sync_budget_to_grant(budget_path, grant_path)

        # Verify grant.yaml was updated
        with open(grant_path) as f:
            updated_grant = yaml.safe_load(f)

        # 100000 + 30000 = 130000 direct, 13000 indirect = 143000
        assert updated_grant["amount_requested"] == 143000

    def test_preserves_other_grant_fields(self, tmp_path):
        """Should preserve other fields in grant.yaml."""
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 50000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.0, "year_1": 0},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            "deadline": "2025-12-01",
            "foundation": "NSF",
            "amount_requested": 0,
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        sync_budget_to_grant(budget_path, grant_path)

        with open(grant_path) as f:
            updated_grant = yaml.safe_load(f)

        assert updated_grant["name"] == "Test Grant"
        assert updated_grant["deadline"] == "2025-12-01"
        assert updated_grant["foundation"] == "NSF"
        assert updated_grant["amount_requested"] == 50000


class TestBudgetValidation:
    """Tests for budget validation."""

    def test_validates_fringe_rate_matches_calculation(self, tmp_path):
        """Should validate that fringe amounts match rate * salaries."""
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 100000}],
                "other": [],
            },
            "fringe_benefits": {
                "rate": 0.30,
                "year_1": 25000,  # Should be 30000 at 30% rate
            },
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.10, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        calc = BudgetCalculator(budget_path)
        warnings = calc.validate()

        assert len(warnings) > 0
        assert any("fringe" in w.lower() for w in warnings)

    def test_validates_indirect_rate_matches_calculation(self, tmp_path):
        """Should warn if indirect costs don't match rate * MTDC."""
        # This test ensures the calculator flags inconsistencies
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 100000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.30, "year_1": 30000},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.10, "base": "mtdc"},
            # If summary.indirect is hardcoded wrong, it should warn
            "summary": {
                "year_1": {"indirect": 5000},  # Should be 13000
            },
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        calc = BudgetCalculator(budget_path)
        warnings = calc.validate()

        # Should flag the inconsistency
        assert any("indirect" in w.lower() for w in warnings)


class TestBudgetCapValidation:
    """Tests for budget cap enforcement."""

    def test_validate_against_caps_passes_when_under(self, tmp_path):
        """Should pass validation when budget is under all caps."""
        budget_yaml = {
            "years_in_budget": 2,
            "personnel": {
                "senior_key": [
                    {"name": "PI", "year_1": 50000, "year_2": 50000}
                ],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.0, "year_1": 0, "year_2": 0},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            "budget_cap": 200000,
            "annual_budget_cap": 100000,
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        calc = BudgetCalculator(budget_path)
        errors = calc.validate_against_caps(grant_path)

        assert len(errors) == 0

    def test_validate_against_caps_fails_when_total_exceeds(self, tmp_path):
        """Should raise error when total budget exceeds cap."""
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 150000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.0, "year_1": 0},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            "budget_cap": 100000,  # Budget is 150k, cap is 100k
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        calc = BudgetCalculator(budget_path)
        errors = calc.validate_against_caps(grant_path)

        assert len(errors) > 0
        assert any("exceeds total cap" in e.lower() for e in errors)

    def test_validate_against_caps_fails_when_annual_exceeds(self, tmp_path):
        """Should raise error when any year exceeds annual cap."""
        budget_yaml = {
            "years_in_budget": 2,
            "personnel": {
                "senior_key": [
                    {"name": "PI", "year_1": 250000, "year_2": 50000}
                ],  # Year 1 over
                "other": [],
            },
            "fringe_benefits": {"rate": 0.0, "year_1": 0, "year_2": 0},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            "budget_cap": 600000,
            "annual_budget_cap": 200000,  # Year 1 is 250k, cap is 200k
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        calc = BudgetCalculator(budget_path)
        errors = calc.validate_against_caps(grant_path)

        assert len(errors) > 0
        assert any(
            "year 1" in e.lower() and "exceeds annual cap" in e.lower()
            for e in errors
        )

    def test_validate_against_caps_reports_all_violations(self, tmp_path):
        """Should report both total and annual cap violations."""
        budget_yaml = {
            "years_in_budget": 3,
            "personnel": {
                "senior_key": [
                    {
                        "name": "PI",
                        "year_1": 250000,
                        "year_2": 250000,
                        "year_3": 250000,
                    }
                ],
                "other": [],
            },
            "fringe_benefits": {
                "rate": 0.0,
                "year_1": 0,
                "year_2": 0,
                "year_3": 0,
            },
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            "budget_cap": 600000,  # Total is 750k
            "annual_budget_cap": 200000,  # Each year is 250k
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        calc = BudgetCalculator(budget_path)
        errors = calc.validate_against_caps(grant_path)

        # Should have total cap error + 3 annual cap errors
        assert len(errors) >= 4
        assert any("exceeds total cap" in e.lower() for e in errors)
        assert any("year 1" in e.lower() for e in errors)
        assert any("year 2" in e.lower() for e in errors)
        assert any("year 3" in e.lower() for e in errors)

    def test_validate_against_caps_skips_if_no_caps_defined(self, tmp_path):
        """Should pass if grant.yaml has no caps defined."""
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 1000000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.0, "year_1": 0},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            # No budget_cap or annual_budget_cap
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        calc = BudgetCalculator(budget_path)
        errors = calc.validate_against_caps(grant_path)

        assert len(errors) == 0


class TestBudgetCapError:
    """Tests for BudgetCapError exception."""

    def test_check_budget_caps_raises_on_violation(self, tmp_path):
        """Should raise BudgetCapError when caps are violated."""
        from grantkit.budget.calculator import (
            BudgetCapError,
            check_budget_caps,
        )

        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 150000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.0, "year_1": 0},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            "budget_cap": 100000,
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        with pytest.raises(BudgetCapError) as exc_info:
            check_budget_caps(budget_path, grant_path)

        assert "exceeds total cap" in str(exc_info.value).lower()

    def test_check_budget_caps_passes_when_valid(self, tmp_path):
        """Should not raise when budget is within caps."""
        from grantkit.budget.calculator import check_budget_caps

        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 50000}],
                "other": [],
            },
            "fringe_benefits": {"rate": 0.0, "year_1": 0},
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        grant_yaml = {
            "name": "Test Grant",
            "budget_cap": 100000,
            "annual_budget_cap": 100000,
        }
        grant_path = tmp_path / "grant.yaml"
        with open(grant_path, "w") as f:
            yaml.dump(grant_yaml, f)

        # Should not raise
        check_budget_caps(budget_path, grant_path)


class TestAutomaticFringeCalculation:
    """Tests for automatic fringe benefit calculation from rate."""

    def test_calculates_fringe_from_rate_when_no_yearly_values(self, tmp_path):
        """Should calculate fringe from rate * salaries when year_N not specified."""
        budget_yaml = {
            "years_in_budget": 2,
            "personnel": {
                "senior_key": [
                    {"name": "PI", "year_1": 100000, "year_2": 100000}
                ],
                "other": [{"title": "RSE", "year_1": 50000, "year_2": 60000}],
            },
            "fringe_benefits": {
                "rate": 0.30,
                # No year_1, year_2 specified - should be calculated
            },
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        calc = BudgetCalculator(budget_path)
        fringe = calc.calculate_fringe_benefits()

        # Year 1: (100000 + 50000) * 0.30 = 45000
        assert fringe["year_1"] == 45000
        # Year 2: (100000 + 60000) * 0.30 = 48000
        assert fringe["year_2"] == 48000
        assert fringe["total"] == 93000

    def test_uses_explicit_fringe_when_provided(self, tmp_path):
        """Should use explicit year_N values when provided."""
        budget_yaml = {
            "years_in_budget": 1,
            "personnel": {
                "senior_key": [{"name": "PI", "year_1": 100000}],
                "other": [],
            },
            "fringe_benefits": {
                "rate": 0.30,
                "year_1": 25000,  # Explicit override (not 30000)
            },
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        calc = BudgetCalculator(budget_path)
        fringe = calc.calculate_fringe_benefits()

        # Should use explicit value, not calculated
        assert fringe["year_1"] == 25000

    def test_mixed_explicit_and_calculated_fringe(self, tmp_path):
        """Should handle mix of explicit and calculated fringe per year."""
        budget_yaml = {
            "years_in_budget": 3,
            "personnel": {
                "senior_key": [
                    {
                        "name": "PI",
                        "year_1": 100000,
                        "year_2": 100000,
                        "year_3": 100000,
                    }
                ],
                "other": [],
            },
            "fringe_benefits": {
                "rate": 0.30,
                "year_1": 25000,  # Explicit
                # year_2 not specified - calculate
                "year_3": 35000,  # Explicit
            },
            "equipment": [],
            "travel": {"domestic": [], "foreign": []},
            "participant_support": [],
            "other_direct_costs": [],
            "indirect_costs": {"rate": 0.0, "base": "mtdc"},
        }
        budget_path = tmp_path / "budget.yaml"
        with open(budget_path, "w") as f:
            yaml.dump(budget_yaml, f)

        calc = BudgetCalculator(budget_path)
        fringe = calc.calculate_fringe_benefits()

        assert fringe["year_1"] == 25000  # Explicit
        assert fringe["year_2"] == 30000  # Calculated: 100000 * 0.30
        assert fringe["year_3"] == 35000  # Explicit

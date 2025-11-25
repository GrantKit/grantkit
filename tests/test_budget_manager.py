"""Tests for budget management functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from grantkit.budget.manager import (
    BudgetItem,
    BudgetManager,
    BudgetSummary,
    GSAPerDiemAPI,
    TravelItem,
)


class TestBudgetItem:
    """Tests for BudgetItem dataclass."""

    def test_basic_item(self):
        """Should create basic budget item."""
        item = BudgetItem(
            description="PI Salary",
            amount=50000,
            category="A",
        )
        assert item.description == "PI Salary"
        assert item.amount == 50000
        assert item.category == "A"

    def test_item_with_justification(self):
        """Should store justification."""
        item = BudgetItem(
            description="Equipment",
            amount=10000,
            category="D",
            justification="Required for data processing",
        )
        assert item.justification == "Required for data processing"


class TestTravelItem:
    """Tests for TravelItem dataclass."""

    def test_basic_travel(self):
        """Should create travel item."""
        travel = TravelItem(
            description="Conference",
            travelers=2,
            days=3,
            destination_city="Washington",
            destination_state="DC",
            fiscal_year=2025,
        )
        assert travel.travelers == 2
        assert travel.days == 3
        assert travel.destination_city == "Washington"


class TestBudgetSummary:
    """Tests for BudgetSummary dataclass."""

    def test_summary_creation(self):
        """Should create budget summary."""
        summary = BudgetSummary(
            direct_costs={"A": 50000, "E": 5000},
            indirect_costs=27500,
            total_costs=82500,
            budget_cap=100000,
            headroom=17500,
            categories={},
            travel_items=[],
        )
        assert summary.total_costs == 82500
        assert summary.headroom == 17500


class TestGSAPerDiemAPI:
    """Tests for GSA Per Diem API client."""

    def test_no_api_key_returns_none(self):
        """Should return None without API key."""
        api = GSAPerDiemAPI(api_key=None)
        lodging, mie = api.get_rates("City", "ST", 2025)
        assert lodging is None
        assert mie is None

    @patch("grantkit.budget.manager.urllib.request.urlopen")
    def test_successful_api_call(self, mock_urlopen):
        """Should parse API response correctly."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "rates": [
                    {
                        "lodging": 200,
                        "meals": 79,
                    }
                ]
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        api = GSAPerDiemAPI(api_key="test-key")
        lodging, mie = api.get_rates("Washington", "DC", 2025)

        assert lodging == 200
        assert mie == 79

    @patch("grantkit.budget.manager.urllib.request.urlopen")
    def test_handles_api_error(self, mock_urlopen):
        """Should handle API errors gracefully."""
        mock_urlopen.side_effect = Exception("Connection error")

        api = GSAPerDiemAPI(api_key="test-key")
        lodging, mie = api.get_rates("City", "ST", 2025)

        assert lodging is None
        assert mie is None


class TestBudgetManager:
    """Tests for BudgetManager class."""

    @pytest.fixture
    def manager(self):
        """Create a BudgetManager instance."""
        return BudgetManager(
            budget_cap=100000,
            indirect_rate=0.50,
        )

    @pytest.fixture
    def sample_budget_yaml(self):
        """Create sample budget YAML content."""
        return {
            "A_senior_personnel": [
                {
                    "description": "PI (2 months)",
                    "amount": 20000,
                    "justification": "2 months summer salary",
                }
            ],
            "B_other_personnel": [
                {"description": "Graduate Student", "amount": 30000}
            ],
            "C_fringe": [{"description": "Fringe at 32%", "amount": 16000}],
            "E_travel": [
                {
                    "description": "Annual Conference",
                    "travelers": 2,
                    "days": 4,
                    "destination": {
                        "city": "Washington",
                        "state": "DC",
                        "fy": 2025,
                    },
                    "airfare": 500,
                }
            ],
        }

    def test_initialization(self, manager):
        """Should initialize with correct values."""
        assert manager.budget_cap == 100000
        assert manager.indirect_rate == 0.50
        assert "A" in manager.categories
        assert "I" in manager.categories

    def test_load_from_yaml(self, manager, sample_budget_yaml):
        """Should load budget from YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(sample_budget_yaml, f)
            f.flush()

            manager.load_from_yaml(Path(f.name))

        assert len(manager.categories["A"]) == 1
        assert len(manager.categories["B"]) == 1
        assert len(manager.travel_items) == 1

    def test_calculate_totals(self, manager, sample_budget_yaml):
        """Should calculate totals correctly."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(sample_budget_yaml, f)
            f.flush()
            manager.load_from_yaml(Path(f.name))

        summary = manager.calculate_totals()

        assert summary.direct_costs["A"] == 20000
        assert summary.direct_costs["B"] == 30000
        assert summary.total_costs > 0
        assert summary.headroom <= manager.budget_cap

    def test_budget_over_cap_warning(self):
        """Should warn when budget exceeds cap."""
        manager = BudgetManager(budget_cap=10000, indirect_rate=0.0)
        manager.categories["A"].append(BudgetItem("PI", 15000, "A"))

        summary = manager.calculate_totals()

        assert len(summary.validation_issues) > 0
        assert any(
            "exceeds" in issue.lower() for issue in summary.validation_issues
        )

    def test_generate_budget_narrative(self, manager, sample_budget_yaml):
        """Should generate narrative document."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(sample_budget_yaml, f)
            f.flush()
            manager.load_from_yaml(Path(f.name))

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "narrative.md"
            manager.generate_budget_narrative(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "Budget" in content
            assert "Senior Personnel" in content

    def test_export_json(self, manager, sample_budget_yaml):
        """Should export to JSON format."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(sample_budget_yaml, f)
            f.flush()
            manager.load_from_yaml(Path(f.name))

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "budget.json"
            manager.export_json(output_path)

            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert "total_costs" in data
            assert "categories" in data
            assert "travel_details" in data


class TestTravelCalculations:
    """Tests for travel cost calculations."""

    def test_travel_cost_calculation(self):
        """Should calculate travel costs correctly."""
        manager = BudgetManager()
        manager.gsa_api.get_rates = MagicMock(return_value=(200, 79))

        travel = TravelItem(
            description="Conference",
            travelers=2,
            days=4,
            destination_city="Washington",
            destination_state="DC",
            fiscal_year=2025,
            airfare_per_person=500,
        )

        manager._calculate_travel_cost(travel)

        # 3 nights lodging + M&IE + airfare for 2 people
        assert travel.total_cost > 0
        assert travel.breakdown["travelers"] == 2
        assert travel.breakdown["nights"] == 3

    def test_single_day_mie(self):
        """Should calculate 75% M&IE for single day trips."""
        manager = BudgetManager()

        travel = TravelItem(
            description="Day Trip",
            travelers=1,
            days=1,
            destination_city="City",
            destination_state="ST",
            fiscal_year=2025,
            lodging_rate=0,
            mie_rate=80,
        )

        manager._calculate_travel_cost(travel)

        # Single day = 75% of M&IE, no overnight stay
        assert travel.breakdown["nights"] == 0
        assert travel.total_cost > 0

    def test_fallback_rates(self):
        """Should use fallback rates when API unavailable."""
        manager = BudgetManager()
        manager.gsa_api.get_rates = MagicMock(return_value=(None, None))

        travel = TravelItem(
            description="Trip",
            travelers=1,
            days=2,
            destination_city="Unknown",
            destination_state="XX",
            fiscal_year=2025,
        )

        manager._calculate_travel_cost(travel)

        # Should use fallback rates
        assert travel.lodging_rate == 200.0  # Default
        assert travel.mie_rate == 79.0  # Default


class TestBudgetManagerEdgeCases:
    """Edge case tests for BudgetManager."""

    def test_missing_yaml_file(self):
        """Should raise error for missing file."""
        manager = BudgetManager()
        with pytest.raises(FileNotFoundError):
            manager.load_from_yaml(Path("/nonexistent/budget.yaml"))

    def test_invalid_yaml(self):
        """Should raise error for invalid YAML."""
        manager = BudgetManager()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(ValueError):
                manager.load_from_yaml(Path(f.name))

    def test_empty_budget(self):
        """Should handle empty budget gracefully."""
        manager = BudgetManager()
        summary = manager.calculate_totals()

        assert summary.total_costs == 0
        assert summary.headroom == manager.budget_cap

    def test_indirect_rate_calculation(self):
        """Should calculate indirect on MTDC correctly."""
        manager = BudgetManager(indirect_rate=0.50)

        # Add items
        manager.categories["A"].append(BudgetItem("PI", 10000, "A"))
        manager.categories["D"].append(BudgetItem("Equipment", 5000, "D"))
        manager.categories["F"].append(BudgetItem("Participant", 2000, "F"))

        summary = manager.calculate_totals()

        # MTDC excludes equipment and participant support
        mtdc_base = 10000  # Only personnel
        expected_indirect = mtdc_base * 0.50
        assert summary.indirect_costs == expected_indirect

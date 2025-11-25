"""Tests for OEWS salary validation."""

from unittest.mock import MagicMock, patch

import pytest

from grantkit.budget.salary_validator import (
    ACADEMIC_OCCUPATION_CODES,
    METRO_AREA_CODES,
    OEWSClient,
    SalaryValidator,
    WageData,
    get_salary_validator,
)


class TestOEWSClient:
    """Tests for OEWSClient."""

    def test_build_series_id_national(self):
        """Should build correct series ID for national data."""
        client = OEWSClient()
        series_id = client._build_series_id(
            "0000000", "15-1252", "mean_annual"
        )
        # Format: OEUM{area}{industry}{occupation}{datatype}
        assert series_id == "OEUM000000000000015125204"

    def test_build_series_id_metro(self):
        """Should build correct series ID for metro area."""
        client = OEWSClient()
        series_id = client._build_series_id("41860", "15-1252", "median")
        assert series_id.startswith("OEUM0041860")
        assert "151252" in series_id
        assert series_id.endswith("08")

    def test_estimate_percentile_at_median(self):
        """Should return ~50 for salary at median."""
        client = OEWSClient()
        wage_data = WageData(
            occupation_code="15-1252",
            occupation_title="Software Developers",
            area_code="0000000",
            area_title="National",
            pct_10=70000,
            pct_25=90000,
            median_annual=120000,
            pct_75=150000,
            pct_90=180000,
        )

        pct = client.estimate_percentile(120000, wage_data)
        assert pct == pytest.approx(50, abs=1)

    def test_estimate_percentile_at_75th(self):
        """Should return ~75 for salary at 75th percentile."""
        client = OEWSClient()
        wage_data = WageData(
            occupation_code="15-1252",
            occupation_title="Software Developers",
            area_code="0000000",
            area_title="National",
            pct_10=70000,
            pct_25=90000,
            median_annual=120000,
            pct_75=150000,
            pct_90=180000,
        )

        pct = client.estimate_percentile(150000, wage_data)
        assert pct == pytest.approx(75, abs=1)

    def test_estimate_percentile_below_10th(self):
        """Should extrapolate below 10th percentile."""
        client = OEWSClient()
        wage_data = WageData(
            occupation_code="15-1252",
            occupation_title="Software Developers",
            area_code="0000000",
            area_title="National",
            pct_10=70000,
            pct_25=90000,
            median_annual=120000,
            pct_75=150000,
            pct_90=180000,
        )

        pct = client.estimate_percentile(35000, wage_data)
        assert pct is not None
        assert pct < 10
        assert pct >= 0

    def test_estimate_percentile_above_90th(self):
        """Should extrapolate above 90th percentile."""
        client = OEWSClient()
        wage_data = WageData(
            occupation_code="15-1252",
            occupation_title="Software Developers",
            area_code="0000000",
            area_title="National",
            pct_10=70000,
            pct_25=90000,
            median_annual=120000,
            pct_75=150000,
            pct_90=180000,
        )

        pct = client.estimate_percentile(250000, wage_data)
        assert pct is not None
        assert pct > 90
        assert pct <= 99

    def test_estimate_percentile_interpolation(self):
        """Should interpolate between percentile points."""
        client = OEWSClient()
        wage_data = WageData(
            occupation_code="15-1252",
            occupation_title="Software Developers",
            area_code="0000000",
            area_title="National",
            pct_25=90000,
            median_annual=120000,
            pct_75=150000,
        )

        # Halfway between 50th (120k) and 75th (150k) should be ~62.5
        pct = client.estimate_percentile(135000, wage_data)
        assert pct is not None
        assert 55 < pct < 70


class TestSalaryValidator:
    """Tests for SalaryValidator."""

    @pytest.fixture
    def mock_wage_data(self):
        """Create mock OEWS wage data for software developers."""
        return WageData(
            occupation_code="15-1252",
            occupation_title="Software Developers",
            area_code="0000000",
            area_title="National",
            mean_annual=130000,
            median_annual=120000,
            pct_10=70000,
            pct_25=90000,
            pct_75=150000,
            pct_90=180000,
        )

    @pytest.fixture
    def validator_with_mock(self, mock_wage_data):
        """Create validator with mocked OEWS client."""
        validator = SalaryValidator()
        validator.oews_client.get_wage_data = MagicMock(
            return_value=mock_wage_data
        )
        return validator

    def test_validate_reasonable_salary(self, validator_with_mock):
        """Should pass for salary at market median."""
        result = validator_with_mock.validate_salary(
            salary=120000,
            occupation="software_developer",
            area="national",
        )

        assert result.is_valid
        assert len(result.issues) == 0
        assert result.percentile == pytest.approx(50, abs=5)

    def test_validate_high_salary_warning(self, validator_with_mock):
        """Should warn for salary above 75th percentile."""
        result = validator_with_mock.validate_salary(
            salary=160000,
            occupation="software_developer",
            area="national",
        )

        assert result.is_valid  # Warning, not error
        assert len(result.warnings) > 0
        assert (
            "above market median" in result.warnings[0].lower()
            or "percentile" in result.warnings[0].lower()
        )

    def test_validate_excessive_salary_error(self, validator_with_mock):
        """Should error for salary above 95th percentile."""
        result = validator_with_mock.validate_salary(
            salary=250000,
            occupation="software_developer",
            area="national",
        )

        assert not result.is_valid
        assert len(result.issues) > 0
        assert "percentile" in result.issues[0].lower()

    def test_validate_low_salary_warning(self, validator_with_mock):
        """Should warn for unusually low salary."""
        result = validator_with_mock.validate_salary(
            salary=35000,
            occupation="software_developer",
            area="national",
        )

        assert result.is_valid  # Low is not an error, just a warning
        assert len(result.warnings) > 0
        assert "low" in result.warnings[0].lower()

    def test_annualize_monthly_salary(self, validator_with_mock):
        """Should annualize salary when months < 12."""
        # 3 months at 30,000 = 120,000/year
        result = validator_with_mock.validate_salary(
            salary=30000,
            occupation="software_developer",
            months=3,
        )

        assert result.salary == 120000  # Annualized
        assert result.is_valid

    def test_resolve_occupation_code(self):
        """Should resolve common occupation names to SOC codes."""
        validator = SalaryValidator()

        assert (
            validator._resolve_occupation_code("software_developer")
            == "15-1252"
        )
        assert (
            validator._resolve_occupation_code("data_scientist") == "15-2051"
        )
        assert validator._resolve_occupation_code("cs_professor") == "25-1021"
        # Pass through already-formatted codes
        assert validator._resolve_occupation_code("15-1252") == "15-1252"

    def test_resolve_area_code(self):
        """Should resolve metro names to BLS area codes."""
        validator = SalaryValidator()

        assert validator._resolve_area_code("national") == "0000000"
        assert validator._resolve_area_code("san_francisco") == "41860"
        assert validator._resolve_area_code("boston") == "14460"
        # Pass through already-formatted codes
        assert validator._resolve_area_code("41860") == "0041860"

    def test_validate_budget_personnel(self, mock_wage_data):
        """Should validate multiple personnel items from budget."""
        validator = SalaryValidator()
        validator.oews_client.get_wage_data = MagicMock(
            return_value=mock_wage_data
        )

        personnel_items = [
            {
                "description": "PI salary (3 months)",
                "amount": 30000,
                "months": 3,
                "occupation": "cs_professor",
            },
            {
                "description": "Software Developer",
                "amount": 120000,
            },
            {
                "description": "Graduate Student",
                "amount": 35000,
            },
        ]

        results = validator.validate_budget_personnel(personnel_items)

        # Should return results for items it can classify
        assert len(results) >= 2

    def test_infer_occupation_from_description(self, mock_wage_data):
        """Should infer occupation from description when not specified."""
        validator = SalaryValidator()
        validator.oews_client.get_wage_data = MagicMock(
            return_value=mock_wage_data
        )

        personnel_items = [
            {"description": "PI salary (3 months)", "amount": 30000},
            {"description": "Postdoctoral researcher", "amount": 60000},
            {"description": "Software developer", "amount": 120000},
        ]

        results = validator.validate_budget_personnel(personnel_items)

        # Should classify PI, postdoc, and developer
        assert len(results) >= 2

    def test_missing_oews_data_warning(self):
        """Should warn when OEWS data unavailable."""
        validator = SalaryValidator()
        validator.oews_client.get_wage_data = MagicMock(return_value=None)

        result = validator.validate_salary(
            salary=100000,
            occupation="software_developer",
        )

        assert result.is_valid  # Don't fail just because data unavailable
        assert len(result.warnings) > 0
        assert "could not fetch" in result.warnings[0].lower()


class TestOccupationCodes:
    """Tests for occupation code constants."""

    def test_software_developer_code(self):
        """Should have correct SOC code for software developer."""
        assert ACADEMIC_OCCUPATION_CODES["software_developer"] == "15-1252"

    def test_cs_professor_code(self):
        """Should have correct SOC code for CS professor."""
        assert ACADEMIC_OCCUPATION_CODES["cs_professor"] == "25-1021"

    def test_postdoc_code(self):
        """Should have SOC code for postdocs."""
        assert "postdoc" in ACADEMIC_OCCUPATION_CODES

    def test_economist_code(self):
        """Should have correct SOC code for economist."""
        assert ACADEMIC_OCCUPATION_CODES["economist"] == "19-3011"


class TestMetroAreaCodes:
    """Tests for metro area code constants."""

    def test_national_code(self):
        """Should have national code."""
        assert METRO_AREA_CODES["national"] == "0000000"

    def test_san_francisco_code(self):
        """Should have SF bay area code."""
        assert METRO_AREA_CODES["san_francisco"] == "41860"

    def test_boston_code(self):
        """Should have Boston metro code."""
        assert METRO_AREA_CODES["boston"] == "14460"

    def test_washington_dc_code(self):
        """Should have DC metro code."""
        assert METRO_AREA_CODES["washington_dc"] == "47900"


class TestGetSalaryValidator:
    """Tests for get_salary_validator factory function."""

    def test_creates_validator(self):
        """Should create a SalaryValidator instance."""
        validator = get_salary_validator()
        assert isinstance(validator, SalaryValidator)

    def test_uses_default_area(self):
        """Should use specified default area."""
        validator = get_salary_validator(default_area="san_francisco")
        assert validator.default_area == "san_francisco"

    def test_uses_env_api_key(self):
        """Should use BLS_API_KEY from environment."""
        with patch.dict("os.environ", {"BLS_API_KEY": "test-key"}):
            validator = get_salary_validator()
            assert validator.oews_client.api_key == "test-key"

    def test_uses_provided_api_key(self):
        """Should use provided API key over environment."""
        validator = get_salary_validator(bls_api_key="provided-key")
        assert validator.oews_client.api_key == "provided-key"

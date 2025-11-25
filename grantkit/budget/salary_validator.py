"""OEWS-based salary validation for NSF grants.

This module validates personnel salaries against Bureau of Labor Statistics
Occupational Employment and Wage Statistics (OEWS) data to ensure proposed
salaries are reasonable and competitive.

NSF requires that salaries be "reasonable and consistent with that paid for
similar work in the applicant's organization." While NSF doesn't strictly
cap salaries at OEWS percentiles, reviewers often flag salaries that
significantly exceed local market rates.
"""

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Common academic/research occupation codes
ACADEMIC_OCCUPATION_CODES = {
    # Computer and Mathematical Occupations
    "computer_scientist": "15-1221",  # Computer and Information Research Scientists
    "software_developer": "15-1252",  # Software Developers
    "data_scientist": "15-2051",  # Data Scientists
    "statistician": "15-2041",  # Statisticians
    "mathematician": "15-2021",  # Mathematicians
    # Life, Physical, and Social Science Occupations
    "economist": "19-3011",  # Economists
    "political_scientist": "19-3094",  # Political Scientists
    "sociologist": "19-3041",  # Sociologists
    "environmental_scientist": "19-2041",  # Environmental Scientists
    "chemist": "19-2031",  # Chemists
    "physicist": "19-2012",  # Physicists
    "biologist": "19-1029",  # Biological Scientists, All Other
    # Engineering
    "engineer": "17-2199",  # Engineers, All Other
    "electrical_engineer": "17-2071",  # Electrical Engineers
    "mechanical_engineer": "17-2141",  # Mechanical Engineers
    "civil_engineer": "17-2051",  # Civil Engineers
    # Education and Training
    "postsecondary_teacher": "25-1000",  # Postsecondary Teachers (broad)
    "cs_professor": "25-1021",  # Computer Science Teachers, Postsecondary
    "engineering_professor": "25-1032",  # Engineering Teachers, Postsecondary
    "math_professor": "25-1022",  # Mathematical Science Teachers, Postsecondary
    "economics_professor": "25-1063",  # Economics Teachers, Postsecondary
    # Research positions
    "research_assistant": "19-4099",  # Life, Physical, and Social Science Technicians
    "postdoc": "19-1099",  # Life Scientists, All Other (often used for postdocs)
}


# BLS area codes for major metro areas
METRO_AREA_CODES = {
    # California
    "san_francisco": "41860",
    "los_angeles": "31080",
    "san_diego": "41740",
    "san_jose": "41940",
    # Northeast
    "new_york": "35620",
    "boston": "14460",
    "philadelphia": "37980",
    "washington_dc": "47900",
    # Midwest
    "chicago": "16980",
    "detroit": "19820",
    "minneapolis": "33460",
    # South
    "atlanta": "12060",
    "dallas": "19100",
    "houston": "26420",
    "austin": "12420",
    "miami": "33100",
    # West
    "seattle": "42660",
    "denver": "19740",
    "phoenix": "38060",
    "portland": "38900",
    # National
    "national": "0000000",
}


@dataclass
class WageData:
    """OEWS wage statistics for an occupation."""

    occupation_code: str
    occupation_title: str
    area_code: str
    area_title: str
    employment: Optional[int] = None
    mean_annual: Optional[float] = None
    median_annual: Optional[float] = None
    pct_10: Optional[float] = None
    pct_25: Optional[float] = None
    pct_75: Optional[float] = None
    pct_90: Optional[float] = None
    year: int = 2023


@dataclass
class SalaryValidationResult:
    """Result of validating a salary against OEWS data."""

    is_valid: bool
    salary: float
    occupation_code: str
    area_code: str
    wage_data: Optional[WageData] = None
    percentile: Optional[float] = None
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class OEWSClient:
    """Client for BLS OEWS (Occupational Employment and Wage Statistics) API."""

    BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    # OEWS series ID format: OEUM{area}{industry}{occupation}{datatype}
    # Area: 7 digits (e.g., 0000000 for national, metro codes)
    # Industry: 6 digits (000000 for cross-industry)
    # Occupation: 6 digits (SOC code)
    # Datatype: 2 digits (01=employment, 04=mean wage, 13=median, etc.)

    DATA_TYPES = {
        "employment": "01",
        "mean_hourly": "03",
        "mean_annual": "04",
        "pct_10": "06",
        "pct_25": "07",
        "median": "08",
        "pct_75": "09",
        "pct_90": "10",
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize OEWS client.

        Args:
            api_key: BLS API key (optional but recommended for higher rate limits)
        """
        self.api_key = api_key
        self._cache: Dict[str, WageData] = {}

    def _build_series_id(
        self, area_code: str, occupation_code: str, data_type: str
    ) -> str:
        """Build BLS OEWS series ID."""
        # Normalize occupation code (remove hyphen)
        occ_code = occupation_code.replace("-", "")

        # Pad area code to 7 digits
        area = area_code.zfill(7)

        # Industry code (cross-industry)
        industry = "000000"

        # Data type code
        dtype = self.DATA_TYPES.get(data_type, "04")

        return f"OEUM{area}{industry}{occ_code}{dtype}"

    def get_wage_data(
        self,
        occupation_code: str,
        area_code: str = "0000000",
        year: int = 2023,
    ) -> Optional[WageData]:
        """Fetch OEWS wage data for an occupation and area.

        Args:
            occupation_code: SOC occupation code (e.g., "15-1252")
            area_code: BLS area code (default national)
            year: Data year

        Returns:
            WageData or None if not found
        """
        cache_key = f"{occupation_code}_{area_code}_{year}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build series IDs for different wage measures
        series_ids = []
        for dtype in [
            "mean_annual",
            "median",
            "pct_10",
            "pct_25",
            "pct_75",
            "pct_90",
        ]:
            series_ids.append(
                self._build_series_id(area_code, occupation_code, dtype)
            )

        try:
            # Build request
            data = {
                "seriesid": series_ids,
                "startyear": str(year),
                "endyear": str(year),
            }

            if self.api_key:
                data["registrationkey"] = self.api_key

            # Make request
            request_data = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                self.BASE_URL,
                data=request_data,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            if result.get("status") != "REQUEST_SUCCEEDED":
                logger.warning(
                    f"BLS API request failed: {result.get('message')}"
                )
                return None

            # Parse results
            wage_data = WageData(
                occupation_code=occupation_code,
                occupation_title="",
                area_code=area_code,
                area_title="",
                year=year,
            )

            for series in result.get("Results", {}).get("series", []):
                series_id = series.get("seriesID", "")
                data_points = series.get("data", [])

                if not data_points:
                    continue

                # Get the value for the requested year
                value = None
                for dp in data_points:
                    if dp.get("year") == str(year):
                        try:
                            value = float(
                                dp.get("value", "0").replace(",", "")
                            )
                        except ValueError:
                            continue
                        break

                if value is None:
                    continue

                # Determine which field this is based on series ID suffix
                if series_id.endswith("04"):
                    wage_data.mean_annual = value
                elif series_id.endswith("08"):
                    wage_data.median_annual = value
                elif series_id.endswith("06"):
                    wage_data.pct_10 = value
                elif series_id.endswith("07"):
                    wage_data.pct_25 = value
                elif series_id.endswith("09"):
                    wage_data.pct_75 = value
                elif series_id.endswith("10"):
                    wage_data.pct_90 = value

            self._cache[cache_key] = wage_data
            return wage_data

        except Exception as e:
            logger.warning(f"Failed to fetch OEWS data: {e}")
            return None

    def estimate_percentile(
        self, salary: float, wage_data: WageData
    ) -> Optional[float]:
        """Estimate the percentile rank of a given salary.

        Uses linear interpolation between known percentile points.

        Args:
            salary: Annual salary to evaluate
            wage_data: OEWS wage data with percentile information

        Returns:
            Estimated percentile (0-100) or None if insufficient data
        """
        # Build percentile points we have
        points = []
        if wage_data.pct_10:
            points.append((10, wage_data.pct_10))
        if wage_data.pct_25:
            points.append((25, wage_data.pct_25))
        if wage_data.median_annual:
            points.append((50, wage_data.median_annual))
        if wage_data.pct_75:
            points.append((75, wage_data.pct_75))
        if wage_data.pct_90:
            points.append((90, wage_data.pct_90))

        if len(points) < 2:
            return None

        # Sort by wage value
        points.sort(key=lambda x: x[1])

        # Find where salary falls
        if salary <= points[0][1]:
            # Below 10th percentile - extrapolate
            return max(0, points[0][0] * (salary / points[0][1]))

        if salary >= points[-1][1]:
            # Above 90th percentile - extrapolate
            # Assume 99th percentile is ~1.5x the 90th
            pct_99_estimate = points[-1][1] * 1.5
            excess_ratio = (salary - points[-1][1]) / (
                pct_99_estimate - points[-1][1]
            )
            return min(99, points[-1][0] + (99 - points[-1][0]) * excess_ratio)

        # Interpolate between known points
        for i in range(len(points) - 1):
            if points[i][1] <= salary <= points[i + 1][1]:
                lower_pct, lower_wage = points[i]
                upper_pct, upper_wage = points[i + 1]
                ratio = (salary - lower_wage) / (upper_wage - lower_wage)
                return lower_pct + ratio * (upper_pct - lower_pct)

        return None


class SalaryValidator:
    """Validates personnel salaries against OEWS market data."""

    # Thresholds for validation
    WARNING_PERCENTILE = 75  # Warn if above 75th percentile
    ERROR_PERCENTILE = 95  # Error if above 95th percentile
    LOW_WARNING_PERCENTILE = 10  # Warn if below 10th (may indicate error)

    def __init__(
        self, bls_api_key: Optional[str] = None, default_area: str = "national"
    ):
        """Initialize salary validator.

        Args:
            bls_api_key: BLS API key for higher rate limits
            default_area: Default area for validation (metro name or code)
        """
        self.oews_client = OEWSClient(bls_api_key)
        self.default_area = default_area

    def _resolve_area_code(self, area: str) -> str:
        """Resolve area name to BLS area code."""
        if area in METRO_AREA_CODES:
            return METRO_AREA_CODES[area]
        # Assume it's already a code
        return area.zfill(7)

    def _resolve_occupation_code(self, occupation: str) -> str:
        """Resolve occupation name to SOC code."""
        if occupation in ACADEMIC_OCCUPATION_CODES:
            return ACADEMIC_OCCUPATION_CODES[occupation]
        # Assume it's already a code
        return occupation

    def validate_salary(
        self,
        salary: float,
        occupation: str,
        months: float = 12,
        area: Optional[str] = None,
        role_description: Optional[str] = None,
    ) -> SalaryValidationResult:
        """Validate a salary against OEWS market data.

        Args:
            salary: Proposed salary amount
            occupation: Occupation code or common name
            months: Number of months the salary covers (for annualization)
            area: Geographic area (metro name or BLS code)
            role_description: Description for context in messages

        Returns:
            SalaryValidationResult with validation details
        """
        # Annualize salary if needed
        annual_salary = salary * (12 / months) if months != 12 else salary

        occupation_code = self._resolve_occupation_code(occupation)
        area_code = self._resolve_area_code(area or self.default_area)

        result = SalaryValidationResult(
            is_valid=True,
            salary=annual_salary,
            occupation_code=occupation_code,
            area_code=area_code,
        )

        # Fetch wage data
        wage_data = self.oews_client.get_wage_data(occupation_code, area_code)

        if wage_data is None:
            result.warnings.append(
                f"Could not fetch OEWS data for {occupation_code} in area {area_code}. "
                "Unable to validate salary against market rates."
            )
            return result

        result.wage_data = wage_data

        # Calculate percentile
        percentile = self.oews_client.estimate_percentile(
            annual_salary, wage_data
        )
        result.percentile = percentile

        role_name = role_description or occupation

        if percentile is not None:
            if percentile >= self.ERROR_PERCENTILE:
                result.is_valid = False
                result.issues.append(
                    f"Salary for {role_name} (${annual_salary:,.0f}/year) is at the "
                    f"{percentile:.0f}th percentile - significantly above market rate. "
                    "NSF reviewers may question this salary level."
                )
                if wage_data.pct_75:
                    result.suggestions.append(
                        f"Consider reducing to ${wage_data.pct_75:,.0f} (75th percentile) "
                        "or provide strong justification for the higher rate."
                    )

            elif percentile >= self.WARNING_PERCENTILE:
                result.warnings.append(
                    f"Salary for {role_name} (${annual_salary:,.0f}/year) is at the "
                    f"{percentile:.0f}th percentile - above market median. "
                    "Ensure strong justification is provided."
                )

            elif percentile <= self.LOW_WARNING_PERCENTILE:
                result.warnings.append(
                    f"Salary for {role_name} (${annual_salary:,.0f}/year) is at the "
                    f"{percentile:.0f}th percentile - unusually low. "
                    "This may indicate a data entry error or difficulty recruiting."
                )

        # Add market context
        if wage_data.median_annual:
            result.suggestions.append(
                f"Market reference: Median salary for {occupation_code} is "
                f"${wage_data.median_annual:,.0f}/year"
            )

        if wage_data.pct_75 and wage_data.pct_25:
            result.suggestions.append(
                f"Typical range (25th-75th percentile): "
                f"${wage_data.pct_25:,.0f} - ${wage_data.pct_75:,.0f}"
            )

        return result

    def validate_budget_personnel(
        self,
        personnel_items: List[Dict],
        default_area: Optional[str] = None,
    ) -> List[SalaryValidationResult]:
        """Validate all personnel salaries in a budget.

        Args:
            personnel_items: List of personnel budget items with:
                - description: Role description
                - amount: Salary amount
                - occupation: (optional) SOC code or common name
                - months: (optional) Number of months
                - area: (optional) Geographic area
            default_area: Default area if not specified per-item

        Returns:
            List of SalaryValidationResult for each personnel item
        """
        results = []

        for item in personnel_items:
            occupation = item.get("occupation")

            # Try to infer occupation from description
            if not occupation:
                desc_lower = item.get("description", "").lower()
                if (
                    "pi" in desc_lower
                    or "principal investigator" in desc_lower
                ):
                    occupation = "postsecondary_teacher"
                elif "postdoc" in desc_lower:
                    occupation = "postdoc"
                elif "graduate" in desc_lower or "student" in desc_lower:
                    occupation = "research_assistant"
                elif "software" in desc_lower or "developer" in desc_lower:
                    occupation = "software_developer"
                elif "data scientist" in desc_lower:
                    occupation = "data_scientist"
                else:
                    # Skip items we can't classify
                    continue

            result = self.validate_salary(
                salary=item.get("amount", 0),
                occupation=occupation,
                months=item.get("months", 12),
                area=item.get("area", default_area),
                role_description=item.get("description"),
            )
            results.append(result)

        return results


def get_salary_validator(
    bls_api_key: Optional[str] = None, default_area: str = "national"
) -> SalaryValidator:
    """Get a configured salary validator instance.

    Args:
        bls_api_key: BLS API key (uses BLS_API_KEY env var if not provided)
        default_area: Default geographic area

    Returns:
        SalaryValidator instance
    """
    import os

    api_key = bls_api_key or os.environ.get("BLS_API_KEY")

    return SalaryValidator(bls_api_key=api_key, default_area=default_area)

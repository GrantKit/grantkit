"""Budget management with NSF compliance and GSA API integration."""

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from jinja2 import Environment, FileSystemLoader

from ..utils.io import ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class BudgetItem:
    """Single budget line item."""
    description: str
    amount: float
    category: str
    subcategory: Optional[str] = None
    year: Optional[int] = None
    justification: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TravelItem:
    """Travel budget item with per diem calculations."""
    description: str
    travelers: int
    days: int
    destination_city: str
    destination_state: str
    fiscal_year: int
    month: Optional[int] = None
    airfare_per_person: float = 0.0
    lodging_rate: Optional[float] = None
    mie_rate: Optional[float] = None  # Meals & Incidental Expenses
    total_cost: float = 0.0
    breakdown: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetSummary:
    """Complete budget summary."""
    direct_costs: Dict[str, float]
    indirect_costs: float
    total_costs: float
    budget_cap: float
    headroom: float
    categories: Dict[str, List[BudgetItem]]
    travel_items: List[TravelItem]
    validation_issues: List[str] = field(default_factory=list)


class GSAPerDiemAPI:
    """Interface to GSA Per Diem API for travel rate lookups."""
    
    BASE_URL = "https://api.gsa.gov/travel/perdiem/v2/rates"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API key from environment or parameter."""
        self.api_key = api_key or os.environ.get("GSA_API_KEY")
        
    def get_rates(
        self,
        city: str,
        state: str,
        fiscal_year: int,
        month: Optional[int] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """Get lodging and M&IE rates for a location.
        
        Returns:
            (lodging_rate, mie_rate) or (None, None) if failed
        """
        if not self.api_key:
            logger.warning("No GSA API key provided")
            return None, None
            
        try:
            # Build API URL
            url = f"{self.BASE_URL}/city/{urllib.parse.quote(state)}/{urllib.parse.quote(city)}"
            params = {
                'fy': str(fiscal_year),
                'api_key': self.api_key
            }
            
            url_with_params = f"{url}?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url_with_params, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            rates = data.get('rates', [])
            if not rates:
                return None, None
                
            rate_data = rates[0]
            
            # Get M&IE rate
            mie_rate = float(rate_data.get('meals', 0)) if rate_data.get('meals') else None
            
            # Get lodging rate (may be seasonal)
            lodging_rate = None
            if month and 'months' in rate_data:
                month_names = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                              'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                if 1 <= month <= 12:
                    month_key = month_names[month - 1]
                    monthly_data = rate_data['months'].get(month_key, {})
                    lodging_rate = float(monthly_data.get('lodging', 0)) or None
                    
            if lodging_rate is None:
                lodging_rate = float(rate_data.get('lodging', 0)) or None
                
            return lodging_rate, mie_rate
            
        except Exception as e:
            logger.warning(f"Failed to fetch GSA rates for {city}, {state}: {e}")
            return None, None


class BudgetManager:
    """NSF budget management with compliance checking and reporting."""
    
    # NSF budget categories
    NSF_CATEGORIES = {
        'A': 'Senior Personnel',
        'B': 'Other Personnel', 
        'C': 'Fringe Benefits',
        'D': 'Equipment',
        'E': 'Travel',
        'F': 'Participant Support',
        'G': 'Other Direct Costs',
        'I': 'Indirect Costs (F&A)'
    }
    
    def __init__(
        self,
        budget_cap: float = 1_500_000,
        indirect_rate: float = 0.15,
        gsa_api_key: Optional[str] = None
    ):
        """Initialize budget manager.
        
        Args:
            budget_cap: Maximum total budget allowed
            indirect_rate: F&A rate to apply to MTDC
            gsa_api_key: GSA API key for per diem rates
        """
        self.budget_cap = budget_cap
        self.indirect_rate = indirect_rate
        self.gsa_api = GSAPerDiemAPI(gsa_api_key)
        
        self.categories: Dict[str, List[BudgetItem]] = {}
        self.travel_items: List[TravelItem] = []
        
        # Initialize categories
        for cat_code in self.NSF_CATEGORIES:
            self.categories[cat_code] = []
            
    def load_from_yaml(self, yaml_path: Path) -> None:
        """Load budget from YAML specification."""
        if not yaml_path.exists():
            raise FileNotFoundError(f"Budget YAML not found: {yaml_path}")
            
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"Failed to parse budget YAML: {e}")
            
        # Clear existing data
        for cat_code in self.categories:
            self.categories[cat_code].clear()
        self.travel_items.clear()
        
        # Load categories
        for cat_key, items in data.items():
            if not cat_key.startswith(tuple(self.NSF_CATEGORIES.keys())):
                continue
                
            cat_code = cat_key.split('_')[0].upper()
            if cat_code not in self.NSF_CATEGORIES:
                continue
                
            if cat_code == 'E':  # Travel - special handling
                self._load_travel_items(items or [])
            elif cat_code == 'I':  # Indirect - special handling
                self._load_indirect_spec(items or [])
            else:
                self._load_category_items(cat_code, items or [])
                
        logger.info(f"Loaded budget from {yaml_path}")
        
    def _load_category_items(self, category: str, items: List[Dict]) -> None:
        """Load items for a standard budget category."""
        for item_data in items:
            item = BudgetItem(
                description=item_data.get('description', 'Untitled'),
                amount=float(item_data.get('amount', 0)),
                category=category,
                justification=item_data.get('justification')
            )
            self.categories[category].append(item)
            
    def _load_travel_items(self, items: List[Dict]) -> None:
        """Load travel items with per diem calculation."""
        for item_data in items:
            travel = TravelItem(
                description=item_data.get('description', 'Travel'),
                travelers=int(item_data.get('travelers', 1)),
                days=int(item_data.get('days', 1)),
                destination_city=item_data.get('destination', {}).get('city', ''),
                destination_state=item_data.get('destination', {}).get('state', ''),
                fiscal_year=int(item_data.get('destination', {}).get('fy', datetime.now().year)),
                month=item_data.get('destination', {}).get('month'),
                airfare_per_person=float(item_data.get('airfare', 0)),
                lodging_rate=item_data.get('lodging_rate'),
                mie_rate=item_data.get('mie_rate')
            )
            
            # Calculate total cost
            self._calculate_travel_cost(travel)
            self.travel_items.append(travel)
            
            # Add to category E
            travel_item = BudgetItem(
                description=travel.description,
                amount=travel.total_cost,
                category='E',
                metadata=travel.breakdown
            )
            self.categories['E'].append(travel_item)
            
    def _load_indirect_spec(self, items: List[Dict]) -> None:
        """Load indirect cost specification."""
        if items and 'rate' in items[0]:
            self.indirect_rate = float(items[0]['rate'])
            
    def _calculate_travel_cost(self, travel: TravelItem) -> None:
        """Calculate total travel cost including per diem."""
        # Get per diem rates if not provided
        if travel.lodging_rate is None or travel.mie_rate is None:
            lodging, mie = self.gsa_api.get_rates(
                travel.destination_city,
                travel.destination_state,
                travel.fiscal_year,
                travel.month
            )
            
            if travel.lodging_rate is None:
                travel.lodging_rate = lodging or 200.0  # Default fallback
            if travel.mie_rate is None:
                travel.mie_rate = mie or 79.0  # Default fallback
                
        # Calculate per person costs
        nights = max(travel.days - 1, 0)
        lodging_total = nights * travel.lodging_rate
        
        # M&IE calculation: 75% on first and last day, 100% on middle days
        if travel.days <= 1:
            mie_total = 0.75 * travel.mie_rate
        else:
            first_last_days = 2 * 0.75 * travel.mie_rate
            middle_days = max(travel.days - 2, 0) * travel.mie_rate
            mie_total = first_last_days + middle_days
            
        per_person_total = travel.airfare_per_person + lodging_total + mie_total
        travel.total_cost = travel.travelers * per_person_total
        
        # Store breakdown
        travel.breakdown = {
            'travelers': travel.travelers,
            'days': travel.days,
            'nights': nights,
            'lodging_rate': travel.lodging_rate,
            'mie_rate': travel.mie_rate,
            'airfare': travel.airfare_per_person,
            'per_person_subtotal': round(per_person_total, 2),
            'total': round(travel.total_cost, 2)
        }
        
    def calculate_totals(self) -> BudgetSummary:
        """Calculate budget totals and generate summary."""
        # Calculate direct costs by category
        direct_costs = {}
        for cat_code, items in self.categories.items():
            if cat_code != 'I':  # Skip indirect
                direct_costs[cat_code] = sum(item.amount for item in items)
                
        total_direct = sum(direct_costs.values())
        
        # Calculate indirect costs (F&A)
        # MTDC typically excludes equipment >$5K and participant support
        equipment_total = direct_costs.get('D', 0)
        participant_total = direct_costs.get('F', 0)
        mtdc_base = total_direct - equipment_total - participant_total
        
        indirect_total = mtdc_base * self.indirect_rate
        
        # Add calculated indirect to categories
        if not self.categories['I']:
            indirect_item = BudgetItem(
                description=f"F&A at {self.indirect_rate*100:.1f}% on MTDC",
                amount=indirect_total,
                category='I',
                metadata={
                    'rate': self.indirect_rate,
                    'mtdc_base': mtdc_base
                }
            )
            self.categories['I'].append(indirect_item)
        else:
            # Use explicitly specified indirect costs
            indirect_total = sum(item.amount for item in self.categories['I'])
            
        total_cost = total_direct + indirect_total
        headroom = self.budget_cap - total_cost
        
        # Validation
        issues = []
        if total_cost > self.budget_cap:
            issues.append(f"Budget exceeds cap by ${total_cost - self.budget_cap:,.0f}")
            
        if headroom < 0:
            issues.append("Budget is over the allowed limit")
        elif headroom < self.budget_cap * 0.05:  # <5% headroom
            issues.append("Very little budget headroom remaining")
            
        return BudgetSummary(
            direct_costs=direct_costs,
            indirect_costs=indirect_total,
            total_costs=total_cost,
            budget_cap=self.budget_cap,
            headroom=headroom,
            categories=self.categories.copy(),
            travel_items=self.travel_items.copy(),
            validation_issues=issues
        )
        
    def generate_budget_narrative(
        self,
        output_path: Path,
        template_name: str = "budget_narrative.md"
    ) -> None:
        """Generate detailed budget narrative document."""
        summary = self.calculate_totals()
        
        # Setup Jinja2 environment
        templates_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(templates_dir))
        
        try:
            template = env.get_template(template_name)
        except:
            # Fallback to basic template
            template_content = self._get_default_budget_template()
            template = env.from_string(template_content)
            
        # Render template
        content = template.render(
            summary=summary,
            nsf_categories=self.NSF_CATEGORIES,
            generated_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            format_currency=lambda x: f"${x:,.0f}"
        )
        
        # Write output
        ensure_directory(output_path.parent)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info(f"Generated budget narrative: {output_path}")
        
    def export_json(self, output_path: Path) -> None:
        """Export budget data as JSON for external tools."""
        summary = self.calculate_totals()
        
        # Convert to JSON-serializable format
        data = {
            'budget_cap': summary.budget_cap,
            'total_costs': summary.total_costs,
            'direct_costs': summary.direct_costs,
            'indirect_costs': summary.indirect_costs,
            'headroom': summary.headroom,
            'categories': {},
            'travel_details': [
                {
                    'description': t.description,
                    'travelers': t.travelers,
                    'days': t.days,
                    'destination': f"{t.destination_city}, {t.destination_state}",
                    'total_cost': t.total_cost,
                    'breakdown': t.breakdown
                }
                for t in summary.travel_items
            ],
            'validation_issues': summary.validation_issues,
            'generated': datetime.now().isoformat()
        }
        
        # Add category details
        for cat_code, items in summary.categories.items():
            data['categories'][cat_code] = {
                'name': self.NSF_CATEGORIES[cat_code],
                'total': sum(item.amount for item in items),
                'items': [
                    {
                        'description': item.description,
                        'amount': item.amount,
                        'justification': item.justification
                    }
                    for item in items
                ]
            }
            
        ensure_directory(output_path.parent)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"Exported budget JSON: {output_path}")
        
    def _get_default_budget_template(self) -> str:
        """Default budget narrative template."""
        return """# Budget Narrative
Generated: {{ generated_date }}

## Summary
- **Total Budget:** {{ format_currency(summary.total_costs) }}
- **Budget Cap:** {{ format_currency(summary.budget_cap) }}
- **Headroom:** {{ format_currency(summary.headroom) }}

{% if summary.validation_issues %}
### ⚠️ Budget Issues
{% for issue in summary.validation_issues %}
- {{ issue }}
{% endfor %}
{% endif %}

{% for cat_code, cat_name in nsf_categories.items() %}
{% if summary.categories[cat_code] %}
## {{ cat_code }}. {{ cat_name }}
{% for item in summary.categories[cat_code] %}
**{{ item.description }}:** {{ format_currency(item.amount) }}
{% if item.justification %}
*Justification:* {{ item.justification }}
{% endif %}
{% endfor %}

**Subtotal:** {{ format_currency(summary.direct_costs.get(cat_code, 0)) }}
{% endif %}
{% endfor %}

{% if summary.travel_items %}
## Travel Details
{% for travel in summary.travel_items %}
### {{ travel.description }}
- **Travelers:** {{ travel.travelers }}
- **Days:** {{ travel.days }}
- **Destination:** {{ travel.destination_city }}, {{ travel.destination_state }}
- **Total Cost:** {{ format_currency(travel.total_cost) }}
{% endfor %}
{% endif %}

---
**Total Direct Costs:** {{ format_currency(summary.total_costs - summary.indirect_costs) }}  
**Total Indirect Costs:** {{ format_currency(summary.indirect_costs) }}  
**Grand Total:** {{ format_currency(summary.total_costs) }}
"""
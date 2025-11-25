"""NSF formatting rules loader and utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from importlib.resources import as_file, files
except ImportError:
    # Python < 3.9 fallback
    from importlib_resources import as_file, files


@dataclass
class NSFRule:
    """Represents a single NSF formatting rule."""

    rule_id: str
    severity: str  # 'error', 'warning', 'info'
    message: str
    citation: str
    quote: str
    url: str
    suggestion: Optional[str] = None


@dataclass
class NSFValidationRule:
    """NSF validation rule with context."""

    category: str
    requirement: Any  # The actual requirement value
    rule: NSFRule


class NSFRulesLoader:
    """Loads and provides access to NSF PAPPG formatting rules."""

    def __init__(self, rules_file: Optional[Path] = None):
        """Initialize with path to NSF rules YAML file."""
        if rules_file is None:
            # Default to bundled rules file using importlib.resources
            try:
                package_files = files("grantkit")
                rules_resource = (
                    package_files / "data" / "nsf_formatting_rules.yaml"
                )
                # Use as_file to get a proper path
                with as_file(rules_resource) as rules_path:
                    self.rules_file = Path(rules_path)
            except Exception:
                # Fallback to relative path
                self.rules_file = (
                    Path(__file__).parent.parent
                    / "data"
                    / "nsf_formatting_rules.yaml"
                )
        else:
            self.rules_file = rules_file

        self._rules_data: Optional[Dict[str, Any]] = None

    def load_rules(self) -> Dict[str, Any]:
        """Load NSF rules from YAML file."""
        if self._rules_data is None:
            if not self.rules_file.exists():
                raise FileNotFoundError(
                    f"NSF rules file not found: {self.rules_file}"
                )

            with open(self.rules_file, "r", encoding="utf-8") as f:
                self._rules_data = yaml.safe_load(f)

        return self._rules_data

    def get_font_requirements(self) -> Dict[str, Any]:
        """Get font-related NSF requirements."""
        rules = self.load_rules()
        return rules.get("font", {})

    def get_spacing_requirements(self) -> Dict[str, Any]:
        """Get spacing-related NSF requirements."""
        rules = self.load_rules()
        return rules.get("spacing", {})

    def get_margin_requirements(self) -> Dict[str, Any]:
        """Get margin-related NSF requirements."""
        rules = self.load_rules()
        return rules.get("margins", {})

    def get_validation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Get validation rules with NSF citations."""
        rules = self.load_rules()
        return rules.get("validation_rules", {})

    def get_rule_citation(self, rule_name: str) -> Optional[str]:
        """Get NSF citation for a specific rule."""
        validation_rules = self.get_validation_rules()
        rule_data = validation_rules.get(rule_name, {})
        return rule_data.get("citation")

    def get_rule_url(self, rule_name: str) -> Optional[str]:
        """Get NSF URL for a specific rule."""
        validation_rules = self.get_validation_rules()
        rule_data = validation_rules.get(rule_name, {})
        return rule_data.get("url")

    def format_validation_message(self, rule_name: str, **kwargs) -> str:
        """Format a validation message with NSF citation."""
        validation_rules = self.get_validation_rules()
        rule_data = validation_rules.get(rule_name, {})

        if not rule_data:
            return f"Validation error: {rule_name}"

        # Format the message with provided kwargs
        message = rule_data.get("message", "").format(**kwargs)
        citation = rule_data.get("citation", "")
        url = rule_data.get("url", "")

        formatted_lines = [f"❌ {message}"]
        if citation:
            formatted_lines.append(f"   NSF Rule: {citation}")
        if url:
            formatted_lines.append(f"   See: {url}")

        return "\n".join(formatted_lines)

    def get_optimization_settings(self) -> Dict[str, Any]:
        """Get space optimization settings."""
        rules = self.load_rules()
        return rules.get("optimization", {})

    def get_program_config(self, program_name: str) -> Dict[str, Any]:
        """Get program-specific configuration."""
        rules = self.load_rules()
        programs = rules.get("programs", {})
        return programs.get(program_name, {})

    def validate_font_size(self, font_size: int) -> List[str]:
        """Validate font size against NSF requirements."""
        issues = []
        font_reqs = self.get_font_requirements()
        min_size = font_reqs.get("size", {}).get("minimum", 10)

        if font_size < min_size:
            issues.append(
                self.format_validation_message("font_size", size=font_size)
            )

        return issues

    def validate_margins(
        self, top: float, bottom: float, left: float, right: float
    ) -> List[str]:
        """Validate margins against NSF requirements."""
        issues = []
        margin_reqs = self.get_margin_requirements()
        required = margin_reqs.get("all_sides", 1.0)

        if any(margin != required for margin in [top, bottom, left, right]):
            issues.append(
                self.format_validation_message(
                    "margins",
                    margin=f"top={top}, bottom={bottom}, left={left}, right={right}",
                )
            )

        return issues

    def get_nsf_metadata(self) -> Dict[str, str]:
        """Get NSF PAPPG metadata information."""
        rules = self.load_rules()
        return rules.get("metadata", {})


# Global instance for easy access
_nsf_rules_loader = None


def get_nsf_rules() -> NSFRulesLoader:
    """Get global NSF rules loader instance."""
    global _nsf_rules_loader
    if _nsf_rules_loader is None:
        _nsf_rules_loader = NSFRulesLoader()
    return _nsf_rules_loader


def validate_nsf_compliance(config: Dict[str, Any]) -> List[str]:
    """Quick validation helper for NSF compliance."""
    rules = get_nsf_rules()
    issues = []

    # Validate font size if present
    if "font_size" in config:
        issues.extend(rules.validate_font_size(config["font_size"]))

    # Validate margins if present
    if all(
        k in config
        for k in ["margin_top", "margin_bottom", "margin_left", "margin_right"]
    ):
        issues.extend(
            rules.validate_margins(
                config["margin_top"],
                config["margin_bottom"],
                config["margin_left"],
                config["margin_right"],
            )
        )

    return issues

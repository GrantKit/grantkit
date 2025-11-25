"""GrantKit - Professional tools for grant proposal assembly, validation, and AI-assisted writing."""

from .core.assembler import GrantAssembler
from .core.validator import NSFValidator
from .budget.manager import BudgetManager
from .funders.nsf.programs.registry import ProgramRegistry

__version__ = "0.1.0"
__author__ = "PolicyEngine"
__email__ = "hello@policyengine.org"

__all__ = [
    "GrantAssembler",
    "NSFValidator",
    "BudgetManager",
    "ProgramRegistry",
]
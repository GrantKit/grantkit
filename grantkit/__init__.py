"""GrantKit — the linter and compiler for grant proposals.

Grants as files; agents bring the AI. GrantKit is a stateless, local-first
engine: it reads a ``grant.yaml`` plus Markdown responses and lints, compiles,
and reports on them without any cloud service or AI calls.
"""

__version__ = "0.2.1"
__author__ = "PolicyEngine"
__email__ = "hello@policyengine.org"

from .budget.manager import BudgetManager
from .core.assembler import GrantAssembler
from .core.checks import CheckItem, CheckResult, run_checks
from .core.project import GrantProject, SectionState
from .core.status import build_status
from .core.validator import NSFValidator
from .funders.nsf.programs.registry import ProgramRegistry
from .packs import FunderPack, list_pack_ids, load_pack, resolve_pack

__all__ = [
    "__version__",
    # Engine
    "GrantProject",
    "SectionState",
    "run_checks",
    "CheckItem",
    "CheckResult",
    "build_status",
    # Rule packs
    "FunderPack",
    "load_pack",
    "resolve_pack",
    "list_pack_ids",
    # Retained building blocks
    "GrantAssembler",
    "NSFValidator",
    "BudgetManager",
    "ProgramRegistry",
]

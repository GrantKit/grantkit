"""Funder rule packs — the core asset of the GrantKit engine.

A funder rule pack is a declarative YAML file under ``grantkit/data/funders/``
that describes everything the engine needs to lint and scaffold a grant for a
particular funder: metadata, sections and their limits, formatting rules (each
carrying a citation), budget rules, portal quirks, spelling locale, and a review
rubric.

See :mod:`grantkit.packs.schema` for the documented schema and
:mod:`grantkit.packs.registry` for discovery/loading.
"""

from .registry import (
    list_pack_ids,
    load_pack,
    load_pack_dict,
    pack_path,
    resolve_pack,
)
from .schema import (
    BudgetRules,
    FormattingRule,
    FunderPack,
    PackSection,
    PortalQuirks,
    RubricCriterion,
    validate_pack,
)

__all__ = [
    "FunderPack",
    "PackSection",
    "FormattingRule",
    "BudgetRules",
    "PortalQuirks",
    "RubricCriterion",
    "validate_pack",
    "list_pack_ids",
    "load_pack",
    "load_pack_dict",
    "resolve_pack",
    "pack_path",
]

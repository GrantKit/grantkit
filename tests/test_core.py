"""Tests for core GrantKit exports."""

import re

from grantkit import __version__


def test_version():
    """Version is the 0.2.0 engine release."""
    assert re.match(r"\d+\.\d+\.\d+", __version__)


def test_retained_imports():
    """Building blocks kept from the pre-refactor code remain importable."""
    from grantkit import (
        BudgetManager,
        GrantAssembler,
        NSFValidator,
        ProgramRegistry,
    )

    assert GrantAssembler is not None
    assert NSFValidator is not None
    assert BudgetManager is not None
    assert ProgramRegistry is not None


def test_engine_imports():
    """The new engine surface is exported from the top-level package."""
    from grantkit import (
        CheckResult,
        FunderPack,
        GrantProject,
        build_status,
        list_pack_ids,
        resolve_pack,
        run_checks,
    )

    assert GrantProject is not None
    assert CheckResult is not None
    assert FunderPack is not None
    assert callable(run_checks)
    assert callable(build_status)
    assert callable(resolve_pack)
    assert callable(list_pack_ids)

"""Tests for core GrantKit functionality."""

import pytest
from grantkit import __version__


def test_version():
    """Test that version is set."""
    assert __version__ == "0.1.0"


def test_imports():
    """Test that main exports are importable."""
    from grantkit import GrantAssembler, NSFValidator, BudgetManager, ProgramRegistry

    assert GrantAssembler is not None
    assert NSFValidator is not None
    assert BudgetManager is not None
    assert ProgramRegistry is not None

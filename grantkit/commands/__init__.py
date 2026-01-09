"""CLI commands for GrantKit."""

from .auth import auth
from .build import build, count, status, validate, validate_biosketch
from .budget import budget, check_salaries
from .pdf import check_pages, export, pdf, pdf_capabilities
from .project import archive, init, list_archived, new, programs
from .references import check_citations, validate_urls
from .sync import sync

__all__ = [
    # Auth commands
    "auth",
    # Build commands
    "build",
    "count",
    "status",
    "validate",
    "validate_biosketch",
    # Budget commands
    "budget",
    "check_salaries",
    # PDF commands
    "check_pages",
    "export",
    "pdf",
    "pdf_capabilities",
    # Project commands
    "archive",
    "init",
    "list_archived",
    "new",
    "programs",
    # References commands
    "check_citations",
    "validate_urls",
    # Sync commands
    "sync",
]

"""Command-line interface for GrantKit."""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from .commands.auth import auth
from .commands.build import build, count, status, validate, validate_biosketch
from .commands.budget import budget, check_salaries
from .commands.pdf import check_pages, export, pdf, pdf_capabilities
from .commands.project import archive, init, list_archived, new, programs
from .commands.references import check_citations, validate_urls
from .commands.sync import sync
from .utils.io import find_project_root

# Setup rich console and logging
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Setup logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory (auto-detected if not specified)",
)
@click.pass_context
def main(
    ctx: click.Context, verbose: bool, project_root: Optional[Path]
) -> None:
    """GrantKit - Professional tools for grant proposal assembly and validation."""
    setup_logging(verbose)

    # Find or set project root
    if not project_root:
        project_root = find_project_root(Path.cwd())
        if not project_root:
            project_root = Path.cwd()

    ctx.ensure_object(dict)
    ctx.obj["project_root"] = project_root
    ctx.obj["verbose"] = verbose

    if verbose:
        console.print(f"[dim]Using project root: {project_root}[/dim]")


# Register command groups
main.add_command(auth)
main.add_command(sync)

# Register standalone commands
main.add_command(init)
main.add_command(new)
main.add_command(archive)
main.add_command(list_archived)
main.add_command(programs)

main.add_command(build)
main.add_command(count)
main.add_command(status)
main.add_command(validate)
main.add_command(validate_biosketch)

main.add_command(budget)
main.add_command(check_salaries)

main.add_command(export)
main.add_command(pdf)
main.add_command(check_pages)
main.add_command(pdf_capabilities)

main.add_command(check_citations)
main.add_command(validate_urls)


if __name__ == "__main__":
    main()

"""Project management commands for GrantKit (init, new, archive, programs)."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..funders.nsf.programs.registry import ProgramRegistry

console = Console()


@click.command()
@click.argument(
    "program",
    type=click.Choice(
        ["pose-phase-2", "cssi", "career"], case_sensitive=False
    ),
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (defaults to current directory)",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@click.pass_context
def init(
    ctx: click.Context, program: str, output_dir: Optional[Path], force: bool
) -> None:
    """Initialize a new NSF proposal project with templates."""

    if not output_dir:
        output_dir = ctx.obj["project_root"]

    output_dir = output_dir.resolve()

    # Check if directory has existing files
    if not force and output_dir.exists() and any(output_dir.iterdir()):
        existing_files = list(output_dir.iterdir())[:5]  # Show first 5
        console.print(f"[yellow]Directory {output_dir} is not empty.[/yellow]")
        console.print(
            "Existing files:", ", ".join(f.name for f in existing_files)
        )
        if not click.confirm("Continue anyway?"):
            console.print("[red]Cancelled.[/red]")
            return

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing project...", total=None)

            registry = ProgramRegistry()
            registry.export_template(program.lower(), output_dir)

            progress.update(
                task, description="Setting up project structure..."
            )

        console.print(
            f"[green]Successfully initialized {program} project in {output_dir}[/green]"
        )
        console.print("\n[bold]Next steps:[/bold]")
        console.print(
            "1. Edit the configuration in [cyan]nsf_config.yaml[/cyan]"
        )
        console.print(
            "2. Write your proposal sections in [cyan]sections/[/cyan]"
        )
        console.print(
            "3. Customize the budget in [cyan]budget/budget.yaml[/cyan]"
        )
        console.print(
            "4. Run [cyan]grantkit build[/cyan] to generate the proposal"
        )

    except Exception as e:
        console.print(f"[red]Initialization failed: {e}[/red]")
        sys.exit(1)


@click.command()
@click.argument("program", required=False)
@click.argument("name", required=False)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Parent directory for new grant (defaults to current directory)",
)
@click.option("--title", "-t", help="Project title")
@click.option("--org", help="Organization name")
@click.option(
    "--list", "list_programs", is_flag=True, help="List available programs"
)
@click.pass_context
def new(
    ctx: click.Context,
    program: Optional[str],
    name: Optional[str],
    output_dir: Optional[Path],
    title: Optional[str],
    org: Optional[str],
    list_programs: bool,
) -> None:
    """Create a new grant project from an NSF program template.

    Examples:

        grantkit new --list                    # List available programs

        grantkit new pose-phase-2 my-project   # Create POSE Phase II grant

        grantkit new cssi tax-simulator --title "Open Tax Simulator"
    """
    import yaml

    registry = ProgramRegistry()

    # List programs if requested or no arguments provided
    if list_programs or (not program and not name):
        table = Table(title="Available NSF Programs")
        table.add_column("Program ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Budget Cap", justify="right")
        table.add_column("Period", justify="right")
        table.add_column("Page Limit", justify="right")

        for program_id in registry.list_programs():
            config = registry.get_program(program_id)
            table.add_row(
                program_id,
                config.name,
                f"${config.budget_cap:,.0f}",
                f"{config.project_period_years} years",
                (
                    str(config.page_limit_total)
                    if config.page_limit_total
                    else "-"
                ),
            )

        console.print(table)
        console.print(
            "\n[dim]Usage: grantkit new <program-id> <project-name>[/dim]"
        )
        return

    if not program:
        console.print("[red]Program ID required[/red]")
        console.print(
            "[dim]Run 'grantkit new --list' to see available programs[/dim]"
        )
        sys.exit(1)

    if not name:
        console.print("[red]Project name required[/red]")
        console.print(
            f"[dim]Usage: grantkit new {program} <project-name>[/dim]"
        )
        sys.exit(1)

    # Validate program exists
    program = program.lower()
    if program not in registry.list_programs():
        console.print(f"[red]Unknown program: {program}[/red]")
        console.print(
            "[dim]Run 'grantkit new --list' to see available programs[/dim]"
        )
        sys.exit(1)

    # Create project directory
    if not output_dir:
        output_dir = ctx.obj["project_root"]

    project_dir = output_dir / name
    if project_dir.exists():
        console.print(f"[red]Directory already exists: {project_dir}[/red]")
        sys.exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Creating project structure...", total=None
            )

            # Create directory
            project_dir.mkdir(parents=True)

            # Generate grant.yaml
            project_title = (
                title
                or f"[Your {registry.get_program(program).name} Project Title]"
            )
            organization = org or "[Your Organization]"

            progress.update(task, description="Generating grant.yaml...")
            grant_config = registry.generate_grant_yaml(
                program, project_title, organization
            )
            grant_yaml_path = project_dir / "grant.yaml"
            with open(grant_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    grant_config, f, default_flow_style=False, sort_keys=False
                )

            # Export templates
            progress.update(task, description="Creating section templates...")
            registry.export_template(program, project_dir)

            # Generate Data Management Plan
            progress.update(
                task, description="Generating Data Management Plan..."
            )
            attachments_dir = project_dir / "attachments"
            attachments_dir.mkdir(exist_ok=True)
            registry.generate_data_management_plan(
                program, attachments_dir / "data_management_plan.md"
            )

            # Generate Bio Sketch template
            progress.update(
                task, description="Generating bio sketch template..."
            )
            personnel_dir = project_dir / "personnel"
            personnel_dir.mkdir(exist_ok=True)
            registry.generate_bio_sketch_template(
                personnel_dir / "pi_biosketch.md"
            )

            # Create .gitignore
            gitignore_content = """# GrantKit generated files
assembled_proposal.md
proposal.pdf
*.log

# Build artifacts
build/
dist/

# Editor files
.vscode/
.idea/
*.swp
*~

# OS files
.DS_Store
Thumbs.db
"""
            (project_dir / ".gitignore").write_text(gitignore_content)

            # Create README
            program_config = registry.get_program(program)
            readme_content = f"""# {project_title}

**Program:** {program_config.name}
**Budget Cap:** ${program_config.budget_cap:,.0f}
**Period:** {program_config.project_period_years} years

## Quick Start

```bash
# Edit sections in sections/
# Then build the proposal
grantkit build

# Validate NSF compliance
grantkit validate

# Check word/page counts
grantkit count

# Generate PDF
grantkit pdf
```

## Project Structure

```
{name}/
├── grant.yaml              # Main configuration
├── sections/               # Proposal sections (edit these)
├── budget/                 # Budget files
├── attachments/            # Data management plan, etc.
├── personnel/              # Bio sketches
└── references/             # Bibliography (optional)
```

## Solicitation

{program_config.solicitation_url or 'See NSF website for solicitation details.'}

---
*Created with [GrantKit](https://github.com/GrantKit/grantkit)*
"""
            (project_dir / "README.md").write_text(readme_content)

        console.print(
            f"\n[green]Created new {program_config.name} project: {project_dir}[/green]"
        )
        console.print("\n[bold]Project Structure:[/bold]")
        console.print(f"  {name}/")
        console.print(
            "     ├── grant.yaml          [cyan]# Main configuration[/cyan]"
        )
        console.print(
            "     ├── sections/           [cyan]# Write your proposal here[/cyan]"
        )
        console.print(
            "     ├── budget/             [cyan]# Budget specification[/cyan]"
        )
        console.print(
            "     ├── attachments/        [cyan]# Data management plan[/cyan]"
        )
        console.print(
            "     └── personnel/          [cyan]# Bio sketches[/cyan]"
        )

        console.print("\n[bold]Next Steps:[/bold]")
        console.print(f"  1. cd {name}")
        console.print("  2. Edit grant.yaml with your project details")
        console.print("  3. Write sections in sections/")
        console.print(
            "  4. Run [cyan]grantkit count[/cyan] to check word counts"
        )
        console.print(
            "  5. Run [cyan]grantkit validate[/cyan] for NSF compliance"
        )
        console.print(
            "  6. Run [cyan]grantkit build[/cyan] to assemble proposal"
        )

    except Exception as e:
        console.print(f"[red]Failed to create project: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@click.command()
@click.argument("project_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--archive-dir",
    "-d",
    type=click.Path(path_type=Path),
    default="archive",
    help="Directory to store archived projects (default: ./archive)",
)
@click.option(
    "--reason",
    "-r",
    help="Reason for archiving (e.g., 'submitted', 'rejected', 'superseded')",
)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def archive(
    ctx: click.Context,
    project_dir: Path,
    archive_dir: Path,
    reason: Optional[str],
    force: bool,
) -> None:
    """Archive a grant project.

    Moves the project to an archive directory with timestamp and optional reason.
    Useful for preserving old versions before updating with new templates.

    Examples:

        grantkit archive nsf-cssi                     # Archive to ./archive/

        grantkit archive nsf-cssi -r "superseded"    # With reason

        grantkit archive nsf-cssi -d old-grants      # Custom archive dir
    """
    import shutil

    import yaml

    project_dir = Path(project_dir).resolve()
    if not project_dir.exists():
        console.print(f"[red]Directory not found: {project_dir}[/red]")
        sys.exit(1)

    # Try to get project name from grant.yaml
    project_name = project_dir.name
    grant_yaml = project_dir / "grant.yaml"
    if grant_yaml.exists():
        try:
            with open(grant_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            title = config.get("grant", {}).get("title", "")
            if title:
                console.print(f"[bold]Project:[/bold] {title}")
        except Exception:
            pass

    # Generate archive name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    archive_name = f"{project_name}-{timestamp}"
    if reason:
        # Sanitize reason for filename
        safe_reason = reason.lower().replace(" ", "-")[:20]
        archive_name = f"{project_name}-{timestamp}-{safe_reason}"

    # Ensure archive directory exists
    archive_path = Path(archive_dir).resolve()
    archive_path.mkdir(parents=True, exist_ok=True)

    dest_path = archive_path / archive_name

    # Check for conflicts
    if dest_path.exists():
        console.print(f"[red]Archive already exists: {dest_path}[/red]")
        console.print(
            "[dim]Use a different reason or wait until tomorrow[/dim]"
        )
        sys.exit(1)

    # Confirm
    if not force:
        console.print("\n[bold]Archive Details:[/bold]")
        console.print(f"  Source: {project_dir}")
        console.print(f"  Destination: {dest_path}")
        if reason:
            console.print(f"  Reason: {reason}")

        if not click.confirm("\nProceed with archive?"):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        # Move the directory
        shutil.move(str(project_dir), str(dest_path))

        # Create an archive metadata file
        metadata = {
            "original_name": project_name,
            "original_path": str(project_dir),
            "archived_at": datetime.now().isoformat(),
            "reason": reason,
        }
        metadata_path = dest_path / ".archive_metadata.yaml"
        with open(metadata_path, "w", encoding="utf-8") as f:
            yaml.dump(metadata, f, default_flow_style=False)

        console.print(f"\n[green]Archived to: {dest_path}[/green]")
        console.print("\n[dim]The original directory has been moved.[/dim]")

    except Exception as e:
        console.print(f"[red]Archive failed: {e}[/red]")
        sys.exit(1)


@click.command("list-archived")
@click.option(
    "--archive-dir",
    "-d",
    type=click.Path(exists=True, path_type=Path),
    default="archive",
    help="Directory containing archived projects",
)
@click.pass_context
def list_archived(ctx: click.Context, archive_dir: Path) -> None:
    """List archived grant projects."""
    import yaml

    archive_path = Path(archive_dir).resolve()
    if not archive_path.exists():
        console.print(
            f"[yellow]No archive directory found: {archive_path}[/yellow]"
        )
        return

    archived = list(archive_path.iterdir())
    if not archived:
        console.print("[yellow]No archived projects found.[/yellow]")
        return

    table = Table(title="Archived Projects")
    table.add_column("Name", style="bold")
    table.add_column("Archived", justify="right")
    table.add_column("Reason")
    table.add_column("Original Path", style="dim")

    for item in sorted(archived):
        if not item.is_dir():
            continue

        metadata_file = item / ".archive_metadata.yaml"
        archived_at = "-"
        reason = "-"
        original_path = "-"

        if metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = yaml.safe_load(f)
                archived_at = metadata.get("archived_at", "-")[
                    :10
                ]  # Date only
                reason = metadata.get("reason") or "-"
                original_path = metadata.get("original_path", "-")
            except Exception:
                pass

        table.add_row(item.name, archived_at, reason, original_path)

    console.print(table)


@click.command()
@click.pass_context
def programs(ctx: click.Context) -> None:
    """List available NSF program configurations."""

    registry = ProgramRegistry()

    table = Table(title="Available NSF Programs")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Budget Cap", justify="right")
    table.add_column("Period", justify="right")

    for program_id in registry.list_programs():
        config = registry.get_program(program_id)
        table.add_row(
            program_id,
            config.name,
            f"${config.budget_cap:,.0f}",
            f"{config.project_period_years} years",
        )

    console.print(table)

    console.print(
        "\n[dim]Use 'grantkit init <program-id>' to create a new project[/dim]"
    )

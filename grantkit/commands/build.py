"""Build and validation commands for GrantKit."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..core.assembler import GrantAssembler
from ..core.validator import NSFValidator

console = Console()


@click.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (defaults to assembled_proposal.md)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "docx", "pdf"]),
    default="markdown",
    help="Output format",
)
@click.option("--template", help="Custom template name")
@click.pass_context
def build(
    ctx: click.Context,
    output: Optional[Path],
    output_format: str,
    template: Optional[str],
) -> None:
    """Assemble the complete proposal document from sections."""

    project_root = ctx.obj["project_root"]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Loading project configuration...", total=None
            )

            assembler = GrantAssembler(project_root)

            progress.update(task, description="Loading section content...")

            if not output:
                output = project_root / f"assembled_proposal.{output_format}"
                if output_format == "markdown":
                    output = project_root / "assembled_proposal.md"

            template_name = template or "proposal_template.md"

            progress.update(task, description="Assembling document...")

            result = assembler.assemble_document(
                output_path=output,
                template_name=template_name,
                include_toc=True,
                include_metadata=True,
            )

        if result.success:
            console.print(
                f"[green]Successfully assembled proposal: {result.output_path}[/green]"
            )
            console.print(f"[dim]Total words: {result.total_words:,}[/dim]")

            # Show completion status
            complete = sum(1 for s in result.sections if s.is_complete)
            total = len(result.sections)
            console.print(f"[dim]Sections complete: {complete}/{total}[/dim]")

            if result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in result.warnings:
                    console.print(f"  - {warning}")

            # Handle format conversion
            if output_format == "pdf":
                from .pdf import export

                progress.update(task, description="Converting to PDF...")
                # Use the PDF generation functionality
                pdf_output = result.output_path.with_suffix(".pdf")
                ctx.invoke(
                    export,
                    output_format="pdf",
                    output=pdf_output,
                    optimize=True,
                    engine=None,
                    font_size=11,
                )
            elif output_format == "docx":
                progress.update(task, description="Converting to DOCX...")
                console.print(
                    "[yellow]Note: DOCX conversion not yet implemented[/yellow]"
                )

        else:
            console.print("[red]Assembly failed[/red]")
            for error in result.errors:
                console.print(f"  - {error}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@click.command()
@click.option("--section", "-s", help="Check specific section only")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed breakdown")
@click.pass_context
def count(ctx: click.Context, section: Optional[str], verbose: bool) -> None:
    """Show word and page counts for each section.

    Validates against program-specific limits defined in grant.yaml or nsf_config.yaml.
    """
    import yaml

    project_root = ctx.obj["project_root"]

    # Load configuration
    grant_yaml = project_root / "grant.yaml"
    nsf_config = project_root / "nsf_config.yaml"

    config_data = None
    sections_config = []

    if grant_yaml.exists():
        with open(grant_yaml, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        sections_config = config_data.get("sections", [])
    elif nsf_config.exists():
        with open(nsf_config, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        sections_config = config_data.get("sections", [])

    if not sections_config:
        console.print(
            "[yellow]No sections configured. Looking for markdown files...[/yellow]"
        )
        sections_dir = project_root / "sections"
        if sections_dir.exists():
            for md_file in sections_dir.glob("*.md"):
                sections_config.append(
                    {
                        "id": md_file.stem,
                        "title": md_file.stem.replace("_", " ").title(),
                        "file": f"sections/{md_file.name}",
                    }
                )

    if not sections_config:
        console.print("[red]No sections found[/red]")
        sys.exit(1)

    # Calculate counts
    table = Table(title="Section Word Counts")
    table.add_column("Section", style="bold")
    table.add_column("Words", justify="right")
    table.add_column("Pages", justify="right")
    table.add_column("Limit", justify="right")
    table.add_column("Status")

    total_words = 0
    total_pages = 0
    issues = []

    for sec in sections_config:
        if section and sec["id"] != section:
            continue

        file_path = project_root / sec.get("file", f"sections/{sec['id']}.md")
        if not file_path.exists():
            table.add_row(
                sec.get("title", sec["id"]),
                "-",
                "-",
                "-",
                "[red]Missing[/red]",
            )
            if sec.get("required", True):
                issues.append(f"Required section missing: {sec['title']}")
            continue

        content = file_path.read_text(encoding="utf-8")
        word_count = len(content.split())
        # Rough page estimate: ~300 words/page with NSF formatting
        page_count = word_count / 300

        total_words += word_count
        total_pages += page_count

        # Check limits
        word_limit = sec.get("word_limit")
        page_limit = sec.get("page_limit")

        limit_str = "-"
        status = "[green]OK[/green]"
        style = None

        if page_limit:
            limit_str = f"{page_limit} pages"
            if page_count > page_limit:
                status = f"[red]Over by {page_count - page_limit:.1f} pages[/red]"
                style = "red"
                issues.append(
                    f"{sec['title']}: Exceeds {page_limit} page limit by {page_count - page_limit:.1f} pages"
                )
            elif page_count > page_limit * 0.9:
                status = f"[yellow]{page_limit - page_count:.1f} pages left[/yellow]"
        elif word_limit:
            limit_str = f"{word_limit:,} words"
            if word_count > word_limit:
                status = (
                    f"[red]Over by {word_count - word_limit:,} words[/red]"
                )
                style = "red"
                issues.append(
                    f"{sec['title']}: Exceeds {word_limit:,} word limit by {word_count - word_limit:,}"
                )
            elif word_count > word_limit * 0.9:
                status = f"[yellow]{word_limit - word_count:,} words left[/yellow]"

        table.add_row(
            sec.get("title", sec["id"]),
            f"{word_count:,}",
            f"{page_count:.1f}",
            limit_str,
            status,
            style=style,
        )

    console.print(table)

    # Summary
    console.print(
        f"\n[bold]Total:[/bold] {total_words:,} words (~{total_pages:.1f} pages)"
    )

    # Check total page limit
    if config_data:
        total_limit = config_data.get("formatting", {}).get("page_limit")
        if not total_limit:
            total_limit = config_data.get("page_limit_total")

        if total_limit:
            if total_pages > total_limit:
                console.print(
                    f"[red]Exceeds total page limit of {total_limit} by {total_pages - total_limit:.1f} pages[/red]"
                )
            else:
                console.print(
                    f"[green]Within {total_limit} page limit ({total_limit - total_pages:.1f} pages remaining)[/green]"
                )

    if issues:
        console.print("\n[yellow]Issues:[/yellow]")
        for issue in issues:
            console.print(f"  - {issue}")
        sys.exit(1)


@click.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show proposal completion status and statistics."""

    project_root = ctx.obj["project_root"]

    try:
        assembler = GrantAssembler(project_root)
        status_info = assembler.get_completion_status()

        # Main status panel
        panel_content = f"""[bold]Proposal Status[/bold]

Sections: {status_info['complete_sections']}/{status_info['total_sections']} complete ({status_info['completion_percentage']:.1f}%)
Total Words: {status_info['total_words']:,}
"""

        if status_info["required_incomplete"] > 0:
            panel_content += f"Required sections missing: {status_info['required_incomplete']}"
            panel_style = "yellow"
        elif status_info["completion_percentage"] == 100:
            panel_content += "All sections complete!"
            panel_style = "green"
        else:
            panel_style = "blue"

        console.print(Panel(panel_content, style=panel_style))

        # Detailed section table
        table = Table(title="Section Details")
        table.add_column("Section", style="bold")
        table.add_column("Status")
        table.add_column("Words", justify="right")
        table.add_column("Limit", justify="right")

        for section in status_info["sections"]:
            status_icon = (
                "Complete"
                if section["complete"]
                else ("Missing" if section["required"] else "Optional")
            )
            status_text = (
                "[green]Complete[/green]"
                if section["complete"]
                else ("[red]Missing[/red]" if section["required"] else "[dim]Optional[/dim]")
            )

            word_limit_text = (
                str(section["word_limit"]) if section["word_limit"] else "-"
            )

            style = None
            if section["over_limit"]:
                style = "red"
                word_limit_text += " (over)"
            elif not section["complete"] and section["required"]:
                style = "yellow"

            table.add_row(
                section["title"],
                status_text,
                f"{section['word_count']:,}",
                word_limit_text,
                style=style,
            )

        console.print(table)

        # Show next steps
        if status_info["required_incomplete"] > 0:
            console.print("\n[bold]Next Steps:[/bold]")
            for section in status_info["sections"]:
                if section["required"] and not section["complete"]:
                    console.print(
                        f"- Complete section: [cyan]{section['title']}[/cyan]"
                    )

    except Exception as e:
        console.print(f"[red]Status check failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@click.command()
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save validation report to file",
)
@click.pass_context
def validate(ctx: click.Context, strict: bool, output: Optional[Path]) -> None:
    """Run NSF compliance validation on the proposal."""

    project_root = ctx.obj["project_root"]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading proposal content...", total=None)

            assembler = GrantAssembler(project_root)
            assembler.load_all_content()

            # Assemble content for validation
            temp_result = assembler.assemble_document()
            if not temp_result.success:
                console.print(
                    "[red]Cannot validate - assembly failed[/red]"
                )
                sys.exit(1)

            progress.update(task, description="Running validation checks...")

            validator = NSFValidator()

            # Read assembled content
            content = temp_result.output_path.read_text(encoding="utf-8")

            # Run validation
            validation_result = validator.validate_proposal(content)

        # Display results
        if validation_result.passed and not (
            strict and validation_result.warnings_count > 0
        ):
            console.print("[green]All validation checks passed![/green]")
        else:
            status_color = (
                "red" if validation_result.errors_count > 0 else "yellow"
            )
            console.print(
                f"[{status_color}]Validation issues found[/{status_color}]"
            )

        # Summary table
        table = Table(title="Validation Summary")
        table.add_column("Type", style="bold")
        table.add_column("Count", justify="right")

        table.add_row(
            "Errors",
            str(validation_result.errors_count),
            style="red" if validation_result.errors_count > 0 else "green",
        )
        table.add_row(
            "Warnings",
            str(validation_result.warnings_count),
            style=(
                "yellow" if validation_result.warnings_count > 0 else "green"
            ),
        )
        table.add_row("Total Issues", str(len(validation_result.issues)))

        console.print(table)

        # Show issues
        if validation_result.issues:
            console.print("\n[bold]Issues Found:[/bold]")
            for i, issue in enumerate(validation_result.issues, 1):
                icon = (
                    "[red]ERROR[/red]"
                    if issue.severity == "error"
                    else "[yellow]WARN[/yellow]" if issue.severity == "warning" else "[blue]INFO[/blue]"
                )
                color = (
                    "red"
                    if issue.severity == "error"
                    else "yellow" if issue.severity == "warning" else "blue"
                )

                console.print(f"\n{icon} [{color}]{issue.message}[/{color}]")
                if issue.location:
                    console.print(f"   [dim]Location: {issue.location}[/dim]")
                if issue.suggestion:
                    console.print(
                        f"   [dim]Suggestion: {issue.suggestion}[/dim]"
                    )
                if issue.rule:
                    console.print(f"   [dim]Rule: {issue.rule}[/dim]")

        # Save report if requested
        if output:
            report = validator.get_validation_report([validation_result])
            output.write_text(report, encoding="utf-8")
            console.print(f"\n[dim]Report saved to: {output}[/dim]")

        # Exit with error code if validation failed
        if validation_result.errors_count > 0 or (
            strict and validation_result.warnings_count > 0
        ):
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@click.command("validate-biosketch")
@click.argument(
    "file_path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.pass_context
def validate_biosketch(ctx: click.Context, file_path: Optional[Path]) -> None:
    """Validate biographical sketch for NSF compliance.

    Checks for required sections, page limits, and formatting.
    """
    project_root = ctx.obj["project_root"]

    # Find biosketch file
    if not file_path:
        candidates = [
            project_root / "personnel" / "pi_biosketch.md",
            project_root / "biosketch.md",
            project_root / "biographical_sketch.md",
        ]
        for candidate in candidates:
            if candidate.exists():
                file_path = candidate
                break

    if not file_path or not file_path.exists():
        console.print("[red]No biographical sketch found[/red]")
        console.print(
            "[dim]Provide path or place in personnel/pi_biosketch.md[/dim]"
        )
        sys.exit(1)

    content = file_path.read_text(encoding="utf-8")
    validator = NSFValidator()
    result = validator.validate_biographical_sketch(content)

    if result.passed:
        console.print(
            "[green]Biographical sketch validation passed![/green]"
        )
    else:
        console.print("[red]Biographical sketch has issues:[/red]")

    # Show word count
    word_count = len(content.split())
    page_estimate = word_count / 500  # More dense text in biosketches

    console.print("\n[bold]Statistics:[/bold]")
    console.print(f"  Words: {word_count:,}")
    console.print(f"  Estimated pages: {page_estimate:.1f}")
    console.print("  Page limit: 3 pages")

    if page_estimate > 3:
        console.print(
            f"[red]  May exceed 3 page limit by ~{page_estimate - 3:.1f} pages[/red]"
        )

    if result.issues:
        console.print("\n[bold]Issues:[/bold]")
        for issue in result.issues:
            icon = "[red]ERROR[/red]" if issue.severity == "error" else "[yellow]WARN[/yellow]"
            color = "red" if issue.severity == "error" else "yellow"
            console.print(f"  {icon} [{color}]{issue.message}[/{color}]")
            if issue.suggestion:
                console.print(f"      [dim]{issue.suggestion}[/dim]")

    if result.errors_count > 0:
        sys.exit(1)

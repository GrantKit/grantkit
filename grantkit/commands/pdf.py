"""PDF generation and validation commands for GrantKit."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..pdf import NSFProgramConfig, PDFConfig, PDFGenerator, PDFValidator

console = Console()


@click.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["docx", "pdf"]),
    default="pdf",
    help="Export format",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output file path"
)
@click.option(
    "--optimize", is_flag=True, help="Optimize content to fit page limits"
)
@click.option(
    "--engine",
    type=click.Choice(["pandoc", "weasyprint"]),
    help="PDF engine to use (auto-detected if not specified)",
)
@click.option(
    "--font-size",
    type=click.IntRange(10, 12),
    default=11,
    help="Font size in points (10-12)",
)
@click.pass_context
def export(
    ctx: click.Context,
    output_format: str,
    output: Optional[Path],
    optimize: bool,
    engine: Optional[str],
    font_size: int,
) -> None:
    """Export proposal to DOCX or PDF format."""
    from .build import build

    project_root = ctx.obj["project_root"]

    # First ensure we have an assembled proposal
    assembled_path = project_root / "assembled_proposal.md"
    if not assembled_path.exists():
        console.print(
            "[yellow]No assembled proposal found. Building first...[/yellow]"
        )
        # Trigger build
        ctx.invoke(build)

    if not output:
        output = project_root / f"proposal.{output_format}"

    if output_format == "docx":
        console.print("[yellow]DOCX export not yet implemented[/yellow]")
        console.print(
            "Use PDF export instead: grantkit export --format pdf"
        )
        return

    try:
        # Load configuration
        config_path = project_root / "nsf_config.yaml"
        config_data = None
        if config_path.exists():
            import yaml

            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)
            pdf_config = PDFConfig.from_yaml(config_data)
        else:
            pdf_config = PDFConfig()

        # Override with CLI options
        if engine:
            pdf_config.engine = engine
        pdf_config.font_size = font_size
        pdf_config.optimize_space = optimize

        # Load program config if available
        program_config = None
        if config_data and "program" in config_data:
            program_configs = NSFProgramConfig.get_program_configs()
            program_id = config_data["program"].get("id")
            program_config = program_configs.get(program_id)

        # Read markdown content
        markdown_content = assembled_path.read_text(encoding="utf-8")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating PDF...", total=None)

            # Create PDF generator
            generator = PDFGenerator(pdf_config)

            # Check capabilities
            capabilities = generator.get_capability_report()
            if not capabilities["can_generate_pdf"]:
                console.print("[red]PDF generation not available[/red]")
                console.print("\nMissing dependencies:")
                for dep, available in capabilities["dependencies"].items():
                    status = "Available" if available else "Missing"
                    console.print(f"  {status}: {dep}")
                console.print("\nRecommendations:")
                for rec in capabilities["recommendations"]:
                    console.print(f"  - {rec}")
                sys.exit(1)

            progress.update(task, description="Converting markdown to PDF...")

            # Extract title and author from config or content
            title = None
            author = None
            if config_data:
                title = config_data.get("title")
                author = config_data.get("author")

            # Generate PDF
            result = generator.generate_pdf(
                markdown_content=markdown_content,
                output_path=output,
                title=title,
                author=author,
                optimize=optimize,
                validate=True,
                program_config=program_config,
            )

        if result.success:
            console.print(
                f"[green]PDF generated successfully: {result.output_path}[/green]"
            )
            console.print(
                f"[dim]Pages: {result.page_count}, Size: {result.file_size_mb:.1f}MB, Time: {result.generation_time_seconds:.1f}s[/dim]"
            )

            # Show validation results
            if result.validation_result:
                validation = result.validation_result
                if validation.is_valid:
                    console.print(
                        "[green]PDF passed NSF validation[/green]"
                    )
                else:
                    console.print("[yellow]PDF validation issues:[/yellow]")
                    for issue in validation.issues:
                        console.print(f"  - {issue}")

                if validation.warnings:
                    console.print("\n[yellow]Warnings:[/yellow]")
                    for warning in validation.warnings:
                        console.print(f"  - {warning}")

            # Show optimization suggestions
            if result.optimization_suggestions:
                console.print("\n[cyan]Optimization Suggestions:[/cyan]")
                for i, suggestion in enumerate(
                    result.optimization_suggestions[:5], 1
                ):
                    priority_icon = (
                        "HIGH"
                        if suggestion.priority == 1
                        else "MED" if suggestion.priority == 2 else "LOW"
                    )
                    console.print(
                        f"  [{priority_icon}] {suggestion.description}"
                    )
                    console.print(
                        f"     [dim]Section: {suggestion.section}, Savings: ~{suggestion.potential_savings_lines:.1f} lines[/dim]"
                    )

                if len(result.optimization_suggestions) > 5:
                    console.print(
                        f"     [dim]... and {len(result.optimization_suggestions) - 5} more[/dim]"
                    )

            # Show warnings
            if result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in result.warnings:
                    console.print(f"  - {warning}")

        else:
            console.print("[red]PDF generation failed[/red]")
            for error in result.errors:
                console.print(f"  - [red]{error}[/red]")

            if result.log_path:
                console.print(
                    f"\n[dim]See log file for details: {result.log_path}[/dim]"
                )

            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Export failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@click.command()
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output file path"
)
@click.option(
    "--optimize", is_flag=True, help="Optimize content to fit page limits"
)
@click.option(
    "--engine",
    type=click.Choice(["pandoc", "weasyprint"]),
    help="PDF engine to use (auto-detected if not specified)",
)
@click.option(
    "--font-size",
    type=click.IntRange(10, 12),
    default=11,
    help="Font size in points (10-12)",
)
@click.pass_context
def pdf(
    ctx: click.Context,
    output: Optional[Path],
    optimize: bool,
    engine: Optional[str],
    font_size: int,
) -> None:
    """Generate NSF-compliant PDF with optimized formatting."""
    # This is essentially the same as export --format pdf but with a cleaner interface
    ctx.invoke(
        export,
        output_format="pdf",
        output=output,
        optimize=optimize,
        engine=engine,
        font_size=font_size,
    )


@click.command()
@click.option(
    "--format",
    type=click.Choice(["brief", "detailed"]),
    default="brief",
    help="Output format",
)
@click.pass_context
def check_pages(ctx: click.Context, format: str) -> None:
    """Quick page count check for generated PDF."""

    project_root = ctx.obj["project_root"]

    # Look for existing PDF
    pdf_candidates = [
        project_root / "proposal.pdf",
        project_root / "assembled_proposal.pdf",
    ]

    pdf_path = None
    for candidate in pdf_candidates:
        if candidate.exists():
            pdf_path = candidate
            break

    if not pdf_path:
        console.print(
            "[yellow]No PDF found. Generate one first with:[/yellow]"
        )
        console.print("  grantkit pdf")
        return

    try:
        # Create validator and check pages
        validator = PDFValidator()
        page_count = validator.count_pages(pdf_path)

        if page_count == 0:
            console.print(f"[red]Could not count pages in {pdf_path}[/red]")
            return

        # Load program config for page limits
        config_path = project_root / "nsf_config.yaml"
        page_limit = None

        if config_path.exists():
            import yaml

            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)

            if config_data and "program" in config_data:
                program_configs = NSFProgramConfig.get_program_configs()
                program_id = config_data["program"].get("id")
                program_config = program_configs.get(program_id)
                if program_config:
                    page_limit = program_config.page_limit

        # Display results
        if format == "brief":
            if page_limit:
                status_color = (
                    "red"
                    if page_count > page_limit
                    else "yellow" if page_count > page_limit * 0.9 else "green"
                )
                console.print(
                    f"[{status_color}]Pages: {page_count}/{page_limit}[/{status_color}]"
                )
                if page_count > page_limit:
                    console.print(
                        f"[red]Exceeds limit by {page_count - page_limit} pages[/red]"
                    )
                elif page_count > page_limit * 0.9:
                    console.print(
                        f"[yellow]Close to limit ({page_limit - page_count} pages remaining)[/yellow]"
                    )
            else:
                console.print(f"Pages: {page_count} (no limit configured)")
        else:
            # Detailed format
            validation_result = validator.validate_pdf(pdf_path, page_limit)

            table = Table(title="PDF Information")
            table.add_column("Property", style="bold")
            table.add_column("Value")

            table.add_row("File", str(pdf_path.name))
            table.add_row("Page Count", str(validation_result.page_count))
            table.add_row(
                "File Size", f"{validation_result.file_size_mb:.1f} MB"
            )

            if page_limit:
                table.add_row("Page Limit", str(page_limit))
                table.add_row(
                    "Pages Remaining",
                    str(page_limit - validation_result.page_count),
                )

            table.add_row(
                "NSF Compliant",
                "Yes" if validation_result.is_valid else "No",
            )

            console.print(table)

            if validation_result.issues:
                console.print("\n[red]Issues:[/red]")
                for issue in validation_result.issues:
                    console.print(f"  - {issue}")

            if validation_result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in validation_result.warnings:
                    console.print(f"  - {warning}")

    except Exception as e:
        console.print(f"[red]Page count check failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()


@click.command()
@click.pass_context
def pdf_capabilities(ctx: click.Context) -> None:
    """Check PDF generation capabilities and dependencies."""

    generator = PDFGenerator()
    capabilities = generator.get_capability_report()

    # Main status
    if capabilities["can_generate_pdf"]:
        console.print("[green]PDF generation is available[/green]")
        console.print(
            f"[dim]Preferred engine: {capabilities['preferred_engine']}[/dim]"
        )
    else:
        console.print("[red]PDF generation is not available[/red]")

    # Dependencies table
    table = Table(title="Dependencies")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Purpose")

    dependency_info = {
        "pandoc": "Markdown to LaTeX conversion (preferred)",
        "xelatex": "LaTeX to PDF compilation (best quality)",
        "weasyprint": "HTML to PDF conversion (fallback)",
        "pypdf": "PDF validation and page counting",
    }

    for dep, available in capabilities["dependencies"].items():
        status = (
            "[green]Available[/green]"
            if available
            else "[red]Missing[/red]"
        )
        purpose = dependency_info.get(dep, "PDF processing")
        table.add_row(dep, status, purpose)

    console.print(table)

    # Recommendations
    if capabilities["recommendations"]:
        console.print("\n[cyan]Recommendations:[/cyan]")
        for rec in capabilities["recommendations"]:
            console.print(f"  - {rec}")

    # Installation instructions
    if not capabilities["can_generate_pdf"]:
        console.print("\n[bold]Installation Instructions:[/bold]")

        if not capabilities["dependencies"]["pandoc"]:
            console.print("\n[cyan]Install Pandoc:[/cyan]")
            console.print("  - macOS: brew install pandoc")
            console.print("  - Ubuntu/Debian: apt-get install pandoc")
            console.print(
                "  - Windows: Download from https://pandoc.org/installing.html"
            )

        if not capabilities["dependencies"]["xelatex"]:
            console.print("\n[cyan]Install LaTeX:[/cyan]")
            console.print("  - macOS: brew install --cask mactex")
            console.print("  - Ubuntu/Debian: apt-get install texlive-full")
            console.print(
                "  - Windows: Download MiKTeX from https://miktex.org/"
            )

        if not capabilities["dependencies"]["weasyprint"]:
            console.print("\n[cyan]Install WeasyPrint (fallback):[/cyan]")
            console.print("  - pip install weasyprint")

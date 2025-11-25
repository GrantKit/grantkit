"""Command-line interface for GrantKit."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .budget.manager import BudgetManager
from .core.assembler import GrantAssembler
from .core.validator import NSFValidator
from .funders.nsf.programs.registry import ProgramRegistry
from .pdf import NSFProgramConfig, PDFConfig, PDFGenerator, PDFValidator
from .references import BibliographyGenerator, BibTeXManager, CitationExtractor
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


@main.command()
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
            f"[green]✅ Successfully initialized {program} project in {output_dir}[/green]"
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
        console.print(f"[red]❌ Initialization failed: {e}[/red]")
        sys.exit(1)


@main.command()
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
                f"[green]✅ Successfully assembled proposal: {result.output_path}[/green]"
            )
            console.print(f"[dim]Total words: {result.total_words:,}[/dim]")

            # Show completion status
            complete = sum(1 for s in result.sections if s.is_complete)
            total = len(result.sections)
            console.print(f"[dim]Sections complete: {complete}/{total}[/dim]")

            if result.warnings:
                console.print("\n[yellow]⚠️  Warnings:[/yellow]")
                for warning in result.warnings:
                    console.print(f"  • {warning}")

            # Handle format conversion
            if output_format == "pdf":
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
            console.print("[red]❌ Assembly failed[/red]")
            for error in result.errors:
                console.print(f"  • {error}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]❌ Build failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
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
                    "[red]❌ Cannot validate - assembly failed[/red]"
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
            console.print("[green]✅ All validation checks passed![/green]")
        else:
            status_color = (
                "red" if validation_result.errors_count > 0 else "yellow"
            )
            console.print(
                f"[{status_color}]⚠️  Validation issues found[/{status_color}]"
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
                    "❌"
                    if issue.severity == "error"
                    else "⚠️" if issue.severity == "warning" else "ℹ️"
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
        console.print(f"[red]❌ Validation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for budget files",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "both"]),
    default="both",
    help="Output format",
)
@click.pass_context
def budget(
    ctx: click.Context, output_dir: Optional[Path], output_format: str
) -> None:
    """Build and validate the project budget."""

    project_root = ctx.obj["project_root"]

    if not output_dir:
        output_dir = project_root / "budget"

    # Look for budget YAML
    budget_yaml = project_root / "budget" / "budget.yaml"
    if not budget_yaml.exists():
        # Try alternative locations
        alt_locations = [
            project_root / "budget.yaml",
            project_root / "docs" / "budget.yaml",
        ]
        for alt in alt_locations:
            if alt.exists():
                budget_yaml = alt
                break
        else:
            console.print(
                f"[red]❌ Budget YAML not found. Expected: {budget_yaml}[/red]"
            )
            console.print(
                "Run [cyan]grantkit init[/cyan] to create a template"
            )
            sys.exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Loading budget specification...", total=None
            )

            manager = BudgetManager()
            manager.load_from_yaml(budget_yaml)

            progress.update(task, description="Calculating totals...")

            summary = manager.calculate_totals()

            progress.update(task, description="Generating reports...")

            # Generate outputs
            if output_format in ["markdown", "both"]:
                md_path = output_dir / "budget_narrative.md"
                manager.generate_budget_narrative(md_path)

            if output_format in ["json", "both"]:
                json_path = output_dir / "budget.json"
                manager.export_json(json_path)

        # Display summary
        panel_content = f"""[bold]Budget Summary[/bold]

💰 Total Budget: ${summary.total_costs:,.0f}
📊 Budget Cap:   ${summary.budget_cap:,.0f}
📈 Headroom:     ${summary.headroom:,.0f} ({summary.headroom/summary.budget_cap*100:.1f}%)

Direct Costs:   ${summary.total_costs - summary.indirect_costs:,.0f}
Indirect Costs: ${summary.indirect_costs:,.0f}"""

        if summary.headroom < 0:
            panel_style = "red"
            panel_content += f"\n\n[red]⚠️  Over budget by ${abs(summary.headroom):,.0f}[/red]"
        elif summary.headroom < summary.budget_cap * 0.1:
            panel_style = "yellow"
            panel_content += "\n\n[yellow]⚠️  Low headroom remaining[/yellow]"
        else:
            panel_style = "green"

        console.print(Panel(panel_content, style=panel_style))

        # Show validation issues
        if summary.validation_issues:
            console.print("\n[yellow]⚠️  Budget Issues:[/yellow]")
            for issue in summary.validation_issues:
                console.print(f"  • {issue}")

        # Show category breakdown
        if ctx.obj["verbose"]:
            table = Table(title="Budget Categories")
            table.add_column("Category", style="bold")
            table.add_column("Amount", justify="right")
            table.add_column("Percentage", justify="right")

            for cat_code, amount in summary.direct_costs.items():
                if amount > 0:
                    manager_cat_name = BudgetManager.NSF_CATEGORIES.get(
                        cat_code, cat_code
                    )
                    pct = amount / summary.total_costs * 100
                    table.add_row(
                        f"{cat_code}. {manager_cat_name}",
                        f"${amount:,.0f}",
                        f"{pct:.1f}%",
                    )

            if summary.indirect_costs > 0:
                pct = summary.indirect_costs / summary.total_costs * 100
                table.add_row(
                    "I. Indirect Costs",
                    f"${summary.indirect_costs:,.0f}",
                    f"{pct:.1f}%",
                    style="dim",
                )

            console.print(table)

        console.print("\n[green]✅ Budget generated successfully[/green]")
        if output_format in ["markdown", "both"]:
            console.print(
                f"[dim]Narrative: {output_dir / 'budget_narrative.md'}[/dim]"
            )
        if output_format in ["json", "both"]:
            console.print(f"[dim]JSON: {output_dir / 'budget.json'}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Budget generation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
@click.option(
    "--occupation",
    "-o",
    help="Occupation code or name (e.g., 'software_developer', '15-1252')",
)
@click.option(
    "--salary",
    "-s",
    type=float,
    help="Annual salary to validate",
)
@click.option(
    "--months",
    "-m",
    type=float,
    default=12,
    help="Number of months salary covers (for annualization)",
)
@click.option(
    "--area",
    "-a",
    default="national",
    help="Geographic area (e.g., 'san_francisco', 'boston', 'national')",
)
@click.option(
    "--from-budget",
    is_flag=True,
    help="Validate all personnel salaries from budget.yaml",
)
@click.pass_context
def check_salaries(
    ctx: click.Context,
    occupation: Optional[str],
    salary: Optional[float],
    months: float,
    area: str,
    from_budget: bool,
) -> None:
    """Validate salaries against OEWS market data.

    Compares proposed salaries to Bureau of Labor Statistics Occupational
    Employment and Wage Statistics (OEWS) to ensure they are reasonable.

    Examples:
        grantkit check-salaries --salary 150000 --occupation software_developer
        grantkit check-salaries --salary 45000 --months 3 --occupation cs_professor
        grantkit check-salaries --from-budget --area san_francisco
    """
    from .budget.salary_validator import (
        ACADEMIC_OCCUPATION_CODES,
        METRO_AREA_CODES,
        get_salary_validator,
    )

    project_root = ctx.obj["project_root"]

    try:
        validator = get_salary_validator(default_area=area)

        if from_budget:
            # Load budget and validate personnel
            budget_yaml = project_root / "budget" / "budget.yaml"
            if not budget_yaml.exists():
                console.print(
                    f"[red]❌ Budget YAML not found: {budget_yaml}[/red]"
                )
                sys.exit(1)

            import yaml

            with open(budget_yaml) as f:
                budget_data = yaml.safe_load(f)

            # Extract personnel items (category A)
            personnel_items = []
            for key, items in budget_data.items():
                if key.upper().startswith("A"):
                    for item in items or []:
                        personnel_items.append(item)

            if not personnel_items:
                console.print(
                    "[yellow]No personnel items found in budget[/yellow]"
                )
                return

            console.print(
                f"[cyan]Validating {len(personnel_items)} personnel items...[/cyan]\n"
            )

            results = validator.validate_budget_personnel(
                personnel_items, default_area=area
            )

            has_issues = False
            for result in results:
                if result.issues or result.warnings:
                    has_issues = True

                    if result.issues:
                        for issue in result.issues:
                            console.print(f"[red]❌ {issue}[/red]")
                    if result.warnings:
                        for warning in result.warnings:
                            console.print(f"[yellow]⚠️  {warning}[/yellow]")
                    if result.suggestions:
                        for suggestion in result.suggestions:
                            console.print(f"[dim]   💡 {suggestion}[/dim]")
                    console.print()

            if not has_issues:
                console.print(
                    "[green]✅ All personnel salaries are within market range[/green]"
                )

        elif salary and occupation:
            # Validate single salary
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Fetching OEWS data...", total=None)
                result = validator.validate_salary(
                    salary=salary,
                    occupation=occupation,
                    months=months,
                    area=area,
                )

            # Display result
            annual = salary * (12 / months) if months != 12 else salary

            console.print("\n[bold]Salary Validation Result[/bold]")
            console.print(f"Salary: ${annual:,.0f}/year")
            console.print(f"Occupation: {result.occupation_code}")
            console.print(f"Area: {area}")

            if result.percentile:
                console.print(f"Percentile: {result.percentile:.0f}th")

            if result.wage_data and result.wage_data.median_annual:
                console.print(
                    f"Market Median: ${result.wage_data.median_annual:,.0f}"
                )

            console.print()

            if result.is_valid:
                console.print(
                    "[green]✅ Salary is within reasonable range[/green]"
                )
            else:
                console.print(
                    "[red]❌ Salary may be flagged by reviewers[/red]"
                )

            for issue in result.issues:
                console.print(f"[red]  • {issue}[/red]")
            for warning in result.warnings:
                console.print(f"[yellow]  • {warning}[/yellow]")
            for suggestion in result.suggestions:
                console.print(f"[dim]  💡 {suggestion}[/dim]")

        else:
            # Show available occupation codes
            console.print("[bold]Available Occupation Codes:[/bold]\n")

            table = Table()
            table.add_column("Name", style="cyan")
            table.add_column("SOC Code")

            for name, code in sorted(ACADEMIC_OCCUPATION_CODES.items()):
                table.add_row(name, code)

            console.print(table)

            console.print("\n[bold]Available Metro Areas:[/bold]\n")

            table2 = Table()
            table2.add_column("Name", style="cyan")
            table2.add_column("BLS Code")

            for name, code in sorted(METRO_AREA_CODES.items()):
                table2.add_row(name, code)

            console.print(table2)

            console.print(
                "\n[dim]Usage: grantkit check-salaries --salary 100000 "
                "--occupation software_developer --area san_francisco[/dim]"
            )

    except Exception as e:
        console.print(f"[red]❌ Salary validation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
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
        console.print("[yellow]⚠️  DOCX export not yet implemented[/yellow]")
        console.print(
            "Use PDF export instead: nsf-assembler export --format pdf"
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
                console.print("[red]❌ PDF generation not available[/red]")
                console.print("\nMissing dependencies:")
                for dep, available in capabilities["dependencies"].items():
                    status = "✅" if available else "❌"
                    console.print(f"  {status} {dep}")
                console.print("\nRecommendations:")
                for rec in capabilities["recommendations"]:
                    console.print(f"  • {rec}")
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
                f"[green]✅ PDF generated successfully: {result.output_path}[/green]"
            )
            console.print(
                f"[dim]Pages: {result.page_count}, Size: {result.file_size_mb:.1f}MB, Time: {result.generation_time_seconds:.1f}s[/dim]"
            )

            # Show validation results
            if result.validation_result:
                validation = result.validation_result
                if validation.is_valid:
                    console.print(
                        "[green]✅ PDF passed NSF validation[/green]"
                    )
                else:
                    console.print("[yellow]⚠️  PDF validation issues:[/yellow]")
                    for issue in validation.issues:
                        console.print(f"  • {issue}")

                if validation.warnings:
                    console.print("\n[yellow]Warnings:[/yellow]")
                    for warning in validation.warnings:
                        console.print(f"  • {warning}")

            # Show optimization suggestions
            if result.optimization_suggestions:
                console.print("\n[cyan]Optimization Suggestions:[/cyan]")
                for i, suggestion in enumerate(
                    result.optimization_suggestions[:5], 1
                ):
                    priority_icon = (
                        "🔥"
                        if suggestion.priority == 1
                        else "⚡" if suggestion.priority == 2 else "💡"
                    )
                    console.print(
                        f"  {priority_icon} {suggestion.description}"
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
                    console.print(f"  • {warning}")

        else:
            console.print("[red]❌ PDF generation failed[/red]")
            for error in result.errors:
                console.print(f"  • [red]{error}[/red]")

            if result.log_path:
                console.print(
                    f"\n[dim]See log file for details: {result.log_path}[/dim]"
                )

            sys.exit(1)

    except Exception as e:
        console.print(f"[red]❌ Export failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show proposal completion status and statistics."""

    project_root = ctx.obj["project_root"]

    try:
        assembler = GrantAssembler(project_root)
        status_info = assembler.get_completion_status()

        # Main status panel
        panel_content = f"""[bold]Proposal Status[/bold]

📝 Sections: {status_info['complete_sections']}/{status_info['total_sections']} complete ({status_info['completion_percentage']:.1f}%)
📊 Total Words: {status_info['total_words']:,}
"""

        if status_info["required_incomplete"] > 0:
            panel_content += f"⚠️  Required sections missing: {status_info['required_incomplete']}"
            panel_style = "yellow"
        elif status_info["completion_percentage"] == 100:
            panel_content += "✅ All sections complete!"
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
                "✅"
                if section["complete"]
                else ("❌" if section["required"] else "⚪")
            )
            status_text = (
                "Complete"
                if section["complete"]
                else ("Missing" if section["required"] else "Optional")
            )

            word_limit_text = (
                str(section["word_limit"]) if section["word_limit"] else "—"
            )

            style = None
            if section["over_limit"]:
                style = "red"
                word_limit_text += " ⚠️"
            elif not section["complete"] and section["required"]:
                style = "yellow"

            table.add_row(
                section["title"],
                f"{status_icon} {status_text}",
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
                        f"• Complete section: [cyan]{section['title']}[/cyan]"
                    )

    except Exception as e:
        console.print(f"[red]❌ Status check failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
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


@main.command()
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


@main.command()
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
        console.print("  nsf-assembler pdf")
        return

    try:
        # Create validator and check pages
        validator = PDFValidator()
        page_count = validator.count_pages(pdf_path)

        if page_count == 0:
            console.print(f"[red]❌ Could not count pages in {pdf_path}[/red]")
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
                        f"[red]❌ Exceeds limit by {page_count - page_limit} pages[/red]"
                    )
                elif page_count > page_limit * 0.9:
                    console.print(
                        f"[yellow]⚠️  Close to limit ({page_limit - page_count} pages remaining)[/yellow]"
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
                "✅ Yes" if validation_result.is_valid else "❌ No",
            )

            console.print(table)

            if validation_result.issues:
                console.print("\n[red]Issues:[/red]")
                for issue in validation_result.issues:
                    console.print(f"  • {issue}")

            if validation_result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in validation_result.warnings:
                    console.print(f"  • {warning}")

    except Exception as e:
        console.print(f"[red]❌ Page count check failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()


@main.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save citation report to file",
)
@click.option(
    "--unused-only", is_flag=True, help="Show only unused bibliography entries"
)
@click.option(
    "--missing-only", is_flag=True, help="Show only missing citation keys"
)
@click.pass_context
def check_citations(
    ctx: click.Context,
    output: Optional[Path],
    unused_only: bool,
    missing_only: bool,
) -> None:
    """Check citations and bibliography for completeness and consistency."""

    project_root = ctx.obj["project_root"]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading bibliography...", total=None)

            # Initialize managers
            bibtex_manager = BibTeXManager(project_root)
            citation_extractor = CitationExtractor()

            # Load bibliography
            bibtex_manager.load_bibliography()

            progress.update(
                task, description="Extracting citations from content..."
            )

            # Generate citation report
            citation_report = citation_extractor.generate_citation_report(
                project_root, bibtex_manager.get_all_keys()
            )

        # Display results
        if not citation_report.citation_keys and not bibtex_manager.entries:
            console.print(
                "[yellow]No citations or bibliography entries found[/yellow]"
            )
            return

        # Summary panel
        panel_content = f"""[bold]Citation Analysis Summary[/bold]

📚 Total Bibliography Entries: {len(bibtex_manager.entries)}
🔗 Total Citations Found: {citation_report.total_citations}
🆔 Unique Citation Keys: {citation_report.unique_citations}
❌ Missing Bibliography Entries: {len(citation_report.missing_entries)}
📋 Unused Bibliography Entries: {len(citation_report.unused_entries)}
📄 Files with Citations: {len(citation_report.citations_by_file)}"""

        if citation_report.missing_entries or citation_report.unused_entries:
            panel_style = "yellow"
        else:
            panel_style = "green"
            panel_content += "\n\n✅ All citations properly referenced!"

        console.print(Panel(panel_content, style=panel_style))

        # Show missing entries
        if citation_report.missing_entries and not unused_only:
            console.print(
                f"\n[red]❌ Missing Bibliography Entries ({len(citation_report.missing_entries)}):[/red]"
            )
            table = Table()
            table.add_column("Citation Key", style="red")
            table.add_column("Used In Files")

            for key in sorted(citation_report.missing_entries):
                files_with_key = []
                for (
                    file_path,
                    citations,
                ) in citation_report.citations_by_file.items():
                    if any(c.citation_key == key for c in citations):
                        files_with_key.append(Path(file_path).name)

                table.add_row(key, ", ".join(files_with_key))

            console.print(table)

        # Show unused entries
        if citation_report.unused_entries and not missing_only:
            console.print(
                f"\n[yellow]📋 Unused Bibliography Entries ({len(citation_report.unused_entries)}):[/yellow]"
            )
            table = Table()
            table.add_column("Bibliography Key", style="yellow")
            table.add_column("Title")
            table.add_column("Authors")

            for key in sorted(citation_report.unused_entries):
                entry = bibtex_manager.get_entry(key)
                title = (
                    entry.title[:60] + "..."
                    if entry and len(entry.title) > 60
                    else entry.title if entry else "Unknown"
                )
                authors = (
                    ", ".join(entry.authors[:2])
                    if entry and entry.authors
                    else "Unknown"
                )
                if entry and len(entry.authors) > 2:
                    authors += " et al."

                table.add_row(key, title, authors)

            console.print(table)

        # Show citations by file if verbose
        if ctx.obj["verbose"] and citation_report.citations_by_file:
            console.print("\n[cyan]Citations by File:[/cyan]")
            for (
                file_path,
                citations,
            ) in citation_report.citations_by_file.items():
                console.print(
                    f"\n[bold]{Path(file_path).name}[/bold] ({len(citations)} citations)"
                )
                for citation in citations[:10]:  # Show first 10
                    console.print(
                        f"  • Line {citation.line_number}: {citation.citation_key}"
                    )
                if len(citations) > 10:
                    console.print(f"  ... and {len(citations) - 10} more")

        # Save report if requested
        if output:
            report_lines = []
            report_lines.append("# Citation Analysis Report")
            report_lines.append(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            report_lines.append("## Summary")
            report_lines.append(
                f"- Total bibliography entries: {len(bibtex_manager.entries)}"
            )
            report_lines.append(
                f"- Total citations: {citation_report.total_citations}"
            )
            report_lines.append(
                f"- Unique citations: {citation_report.unique_citations}"
            )
            report_lines.append(
                f"- Missing entries: {len(citation_report.missing_entries)}"
            )
            report_lines.append(
                f"- Unused entries: {len(citation_report.unused_entries)}\n"
            )

            if citation_report.missing_entries:
                report_lines.append("## Missing Bibliography Entries")
                for key in sorted(citation_report.missing_entries):
                    report_lines.append(f"- {key}")
                report_lines.append("")

            if citation_report.unused_entries:
                report_lines.append("## Unused Bibliography Entries")
                for key in sorted(citation_report.unused_entries):
                    entry = bibtex_manager.get_entry(key)
                    title = entry.title if entry else "Unknown title"
                    report_lines.append(f"- {key}: {title}")

            output.write_text("\n".join(report_lines), encoding="utf-8")
            console.print(f"\n[dim]Report saved to: {output}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Citation check failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
@click.option(
    "--strict",
    is_flag=True,
    help="Use strict validation (treat warnings as errors)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save validation report to file",
)
@click.option(
    "--references-only", is_flag=True, help="Validate only references section"
)
@click.option("--main-only", is_flag=True, help="Validate only main document")
@click.pass_context
def validate_urls(
    ctx: click.Context,
    strict: bool,
    output: Optional[Path],
    references_only: bool,
    main_only: bool,
) -> None:
    """Validate URLs and email addresses for NSF compliance."""

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
                    "[red]❌ Cannot validate - assembly failed[/red]"
                )
                sys.exit(1)

            progress.update(task, description="Reading content...")

            # Read assembled content
            content = temp_result.output_path.read_text(encoding="utf-8")

            validator = NSFValidator()

            progress.update(
                task, description="Running URL/email validation..."
            )

            # Check if we have bibliography capabilities for separated validation
            if not references_only and not main_only:
                try:
                    bibliography_generator = BibliographyGenerator(
                        project_root
                    )
                    main_content, _ = (
                        bibliography_generator.process_content_with_citations(
                            content
                        )
                    )

                    # Generate references content
                    bib_result = bibliography_generator.create_separate_references_document(
                        main_content
                    )
                    references_content = (
                        bib_result.bibliography_content
                        if bib_result.success
                        else ""
                    )

                    # Use separated validation
                    validation_result = validator.validate_separated_content(
                        main_content, references_content
                    )

                    console.print(
                        "[cyan]ℹ️  Using separated document validation[/cyan]"
                    )

                except Exception:
                    # Fall back to regular validation
                    validation_result = validator.validate_proposal(
                        content,
                        check_formatting=False,
                        check_content=False,
                        check_compliance=True,
                    )
                    console.print(
                        "[yellow]⚠️  Using combined document validation[/yellow]"
                    )
            else:
                # Single document validation
                validation_result = validator.validate_proposal(
                    content,
                    check_formatting=False,
                    check_content=False,
                    check_compliance=True,
                )

        # Display results
        if validation_result.passed and not (
            strict and validation_result.warnings_count > 0
        ):
            console.print("[green]✅ URL and email validation passed![/green]")
        else:
            status_color = (
                "red" if validation_result.errors_count > 0 else "yellow"
            )
            console.print(
                f"[{status_color}]⚠️  URL/email validation issues found[/{status_color}]"
            )

        # Summary table
        table = Table(title="URL/Email Validation Summary")
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

        console.print(table)

        # Show issues grouped by type
        if validation_result.issues:
            console.print("\n[bold]Issues Found:[/bold]")

            # Group by category
            by_category = {}
            for issue in validation_result.issues:
                if issue.category not in by_category:
                    by_category[issue.category] = []
                by_category[issue.category].append(issue)

            for category, issues in by_category.items():
                console.print(f"\n[bold]{category.title()} Issues:[/bold]")

                for i, issue in enumerate(issues, 1):
                    icon = (
                        "❌"
                        if issue.severity == "error"
                        else "⚠️" if issue.severity == "warning" else "ℹ️"
                    )
                    color = (
                        "red"
                        if issue.severity == "error"
                        else (
                            "yellow" if issue.severity == "warning" else "blue"
                        )
                    )

                    console.print(
                        f"\n{i}. {icon} [{color}]{issue.message}[/{color}]"
                    )
                    if issue.location:
                        console.print(f"   [dim]📍 {issue.location}[/dim]")
                    if issue.suggestion:
                        console.print(f"   [dim]💡 {issue.suggestion}[/dim]")
                    if issue.rule:
                        console.print(f"   [dim]📋 {issue.rule}[/dim]")

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
        console.print(f"[red]❌ URL validation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@main.command()
@click.pass_context
def pdf_capabilities(ctx: click.Context) -> None:
    """Check PDF generation capabilities and dependencies."""

    generator = PDFGenerator()
    capabilities = generator.get_capability_report()

    # Main status
    if capabilities["can_generate_pdf"]:
        console.print("[green]✅ PDF generation is available[/green]")
        console.print(
            f"[dim]Preferred engine: {capabilities['preferred_engine']}[/dim]"
        )
    else:
        console.print("[red]❌ PDF generation is not available[/red]")

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
            "[green]✅ Available[/green]"
            if available
            else "[red]❌ Missing[/red]"
        )
        purpose = dependency_info.get(dep, "PDF processing")
        table.add_row(dep, status, purpose)

    console.print(table)

    # Recommendations
    if capabilities["recommendations"]:
        console.print("\n[cyan]Recommendations:[/cyan]")
        for rec in capabilities["recommendations"]:
            console.print(f"  • {rec}")

    # Installation instructions
    if not capabilities["can_generate_pdf"]:
        console.print("\n[bold]Installation Instructions:[/bold]")

        if not capabilities["dependencies"]["pandoc"]:
            console.print("\n[cyan]Install Pandoc:[/cyan]")
            console.print("  • macOS: brew install pandoc")
            console.print("  • Ubuntu/Debian: apt-get install pandoc")
            console.print(
                "  • Windows: Download from https://pandoc.org/installing.html"
            )

        if not capabilities["dependencies"]["xelatex"]:
            console.print("\n[cyan]Install LaTeX:[/cyan]")
            console.print("  • macOS: brew install --cask mactex")
            console.print("  • Ubuntu/Debian: apt-get install texlive-full")
            console.print(
                "  • Windows: Download MiKTeX from https://miktex.org/"
            )

        if not capabilities["dependencies"]["weasyprint"]:
            console.print("\n[cyan]Install WeasyPrint (fallback):[/cyan]")
            console.print("  • pip install weasyprint")


@main.group()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Sync grants with Supabase (pull, push, watch)."""
    pass


@sync.command()
@click.option("--grant", "-g", help="Specific grant ID to pull (default: all)")
@click.pass_context
def pull(ctx: click.Context, grant: Optional[str]) -> None:
    """Pull grants and responses from Supabase to local files."""
    from .sync import get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Connecting to Supabase...", total=None)

            sync_client = get_sync_client(project_root)

            progress.update(task, description="Pulling grants...")
            stats = sync_client.pull(grant_id=grant)

        console.print("\n[green]✅ Pull complete![/green]")
        console.print(f"   Grants: {stats['grants']}")
        console.print(f"   Responses: {stats['responses']}")
        console.print(f"   Files written: {stats['files_written']}")

    except ValueError as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        console.print(
            "\n[dim]Set GRANTKIT_SUPABASE_KEY environment variable or create grantkit.yaml[/dim]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Pull failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@sync.command()
@click.option("--grant", "-g", help="Specific grant ID to push (default: all)")
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Run NSF validation before push",
)
@click.pass_context
def push(ctx: click.Context, grant: Optional[str], validate: bool) -> None:
    """Push local files to Supabase."""
    from .sync import get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        # Optionally validate first
        if validate:
            console.print("[dim]Running validation...[/dim]")
            validator = NSFValidator(project_root)
            result = validator.validate()

            if not result.passed:
                console.print(
                    f"\n[yellow]⚠️  Validation found {result.errors_count} errors[/yellow]"
                )
                for issue in result.issues:
                    if issue.severity == "error":
                        console.print(f"   [red]• {issue.message}[/red]")
                if not click.confirm("Continue with push anyway?"):
                    console.print("[red]Push cancelled.[/red]")
                    return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Connecting to Supabase...", total=None)

            sync_client = get_sync_client(project_root)

            progress.update(task, description="Pushing to Supabase...")
            stats = sync_client.push(grant_id=grant)

        console.print("\n[green]✅ Push complete![/green]")
        console.print(f"   Grants: {stats['grants']}")
        console.print(f"   Responses: {stats['responses']}")

        if stats["errors"]:
            console.print(
                f"\n[yellow]⚠️  {len(stats['errors'])} errors occurred:[/yellow]"
            )
            for error in stats["errors"]:
                console.print(f"   [red]• {error}[/red]")

    except ValueError as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        console.print(
            "\n[dim]Set GRANTKIT_SUPABASE_KEY environment variable or create grantkit.yaml[/dim]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Push failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@sync.command()
@click.option(
    "--grant", "-g", help="Specific grant ID to watch (default: all)"
)
@click.pass_context
def watch(ctx: click.Context, grant: Optional[str]) -> None:
    """Watch for file changes and auto-sync to Supabase."""
    from .sync import get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        sync_client = get_sync_client(project_root)

        if grant:
            sync_client.config.grant_id = grant

        console.print(
            f"[green]👀 Watching {project_root} for changes...[/green]"
        )
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        def on_sync(stats):
            console.print(
                f"[green]✓[/green] Synced {stats['responses']} responses"
            )

        sync_client.watch(callback=on_sync)

    except ValueError as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        console.print(
            "\n[dim]Set GRANTKIT_SUPABASE_KEY environment variable or create grantkit.yaml[/dim]"
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Watch failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()

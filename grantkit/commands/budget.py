"""Budget commands for GrantKit."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..budget.calculator import BudgetCalculator

console = Console()


def _generate_budget_narrative(
    summary: dict, budget_cap: float, output_path: Path
) -> None:
    """Generate a budget narrative markdown file from calculator summary."""
    grand_total = summary["grand_total"]
    total_direct = summary["total_direct_costs"]["total"]
    indirect_total = summary["indirect_costs"]["total"]
    headroom = budget_cap - grand_total

    lines = [
        "# Budget Narrative",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        f"- **Total Budget:** ${grand_total:,.0f}",
        f"- **Budget Cap:** ${budget_cap:,.0f}",
        f"- **Headroom:** ${headroom:,.0f}",
        "",
    ]

    # Category sections
    categories = [
        ("A", "Senior Personnel", "senior_personnel"),
        ("B", "Other Personnel", "other_personnel"),
        ("C", "Fringe Benefits", "fringe_benefits"),
        ("D", "Equipment", "equipment"),
        ("E", "Travel", "travel"),
        ("F", "Participant Support", "participant_support"),
        ("G", "Other Direct Costs", "other_direct_costs"),
    ]

    for cat_code, cat_name, key in categories:
        cat_data = summary[key]
        if cat_data["total"] > 0:
            lines.append(f"## {cat_code}. {cat_name}")
            lines.append("")
            for year in range(1, 10):
                year_key = f"year_{year}"
                if year_key in cat_data:
                    lines.append(f"- Year {year}: ${cat_data[year_key]:,}")
            lines.append(f"- **Total:** ${cat_data['total']:,}")
            lines.append("")

    # Indirect costs
    if indirect_total > 0:
        lines.append("## I. Indirect Costs (F&A)")
        lines.append("")
        ind_data = summary["indirect_costs"]
        rate = ind_data.get("rate", 0)
        if rate:
            lines.append(f"Rate: {rate*100:.1f}% on MTDC")
        for year in range(1, 10):
            year_key = f"year_{year}"
            if year_key in ind_data:
                lines.append(f"- Year {year}: ${ind_data[year_key]:,}")
        lines.append(f"- **Total:** ${indirect_total:,}")
        lines.append("")

    # Totals
    lines.extend(
        [
            "---",
            f"**Total Direct Costs:** ${total_direct:,}",
            f"**Total Indirect Costs:** ${indirect_total:,}",
            f"**Grand Total:** ${grand_total:,}",
        ]
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


@click.command()
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
    import json as json_module

    import yaml

    from ..utils.io import ensure_directory

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
                f"[red]Budget YAML not found. Expected: {budget_yaml}[/red]"
            )
            console.print(
                "Run [cyan]grantkit init[/cyan] to create a template"
            )
            sys.exit(1)

    # Load grant.yaml for budget cap
    grant_yaml = project_root / "grant.yaml"
    budget_cap = 1_500_000  # Default NSF cap
    if grant_yaml.exists():
        with open(grant_yaml, "r", encoding="utf-8") as f:
            grant_data = yaml.safe_load(f) or {}
            budget_cap = grant_data.get("budget_cap", budget_cap)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Loading budget specification...", total=None
            )

            calc = BudgetCalculator(budget_yaml)
            summary = calc.get_summary()

            progress.update(task, description="Calculating totals...")

            grand_total = summary["grand_total"]
            total_direct = summary["total_direct_costs"]["total"]
            indirect_total = summary["indirect_costs"]["total"]
            headroom = budget_cap - grand_total

            progress.update(task, description="Generating reports...")

            # Generate outputs
            ensure_directory(output_dir)

            if output_format in ["markdown", "both"]:
                md_path = output_dir / "budget_narrative.md"
                _generate_budget_narrative(summary, budget_cap, md_path)

            if output_format in ["json", "both"]:
                json_path = output_dir / "budget.json"
                json_data = {
                    "budget_cap": budget_cap,
                    "grand_total": grand_total,
                    "total_direct_costs": total_direct,
                    "indirect_costs": indirect_total,
                    "headroom": headroom,
                    "categories": {
                        "A_senior_personnel": summary["senior_personnel"],
                        "B_other_personnel": summary["other_personnel"],
                        "C_fringe_benefits": summary["fringe_benefits"],
                        "D_equipment": summary["equipment"],
                        "E_travel": summary["travel"],
                        "F_participant_support": summary[
                            "participant_support"
                        ],
                        "G_other_direct_costs": summary["other_direct_costs"],
                        "I_indirect_costs": summary["indirect_costs"],
                    },
                    "generated": datetime.now().isoformat(),
                }
                with open(json_path, "w", encoding="utf-8") as f:
                    json_module.dump(json_data, f, indent=2)

        # Display summary
        panel_content = f"""[bold]Budget Summary[/bold]

Total Budget: ${grand_total:,.0f}
Budget Cap:   ${budget_cap:,.0f}
Headroom:     ${headroom:,.0f} ({headroom/budget_cap*100:.1f}%)

Direct Costs:   ${total_direct:,.0f}
Indirect Costs: ${indirect_total:,.0f}"""

        if headroom < 0:
            panel_style = "red"
            panel_content += (
                f"\n\n[red]Over budget by ${abs(headroom):,.0f}[/red]"
            )
        elif headroom < budget_cap * 0.1:
            panel_style = "yellow"
            panel_content += "\n\n[yellow]Low headroom remaining[/yellow]"
        else:
            panel_style = "green"

        console.print(Panel(panel_content, style=panel_style))

        # Show category breakdown
        if ctx.obj["verbose"]:
            table = Table(title="Budget Categories")
            table.add_column("Category", style="bold")
            table.add_column("Amount", justify="right")
            table.add_column("Percentage", justify="right")

            categories = [
                (
                    "A",
                    "Senior Personnel",
                    summary["senior_personnel"]["total"],
                ),
                ("B", "Other Personnel", summary["other_personnel"]["total"]),
                ("C", "Fringe Benefits", summary["fringe_benefits"]["total"]),
                ("D", "Equipment", summary["equipment"]["total"]),
                ("E", "Travel", summary["travel"]["total"]),
                (
                    "F",
                    "Participant Support",
                    summary["participant_support"]["total"],
                ),
                (
                    "G",
                    "Other Direct Costs",
                    summary["other_direct_costs"]["total"],
                ),
            ]

            for cat_code, cat_name, amount in categories:
                if amount > 0:
                    pct = amount / grand_total * 100
                    table.add_row(
                        f"{cat_code}. {cat_name}",
                        f"${amount:,.0f}",
                        f"{pct:.1f}%",
                    )

            if indirect_total > 0:
                pct = indirect_total / grand_total * 100
                table.add_row(
                    "I. Indirect Costs",
                    f"${indirect_total:,.0f}",
                    f"{pct:.1f}%",
                    style="dim",
                )

            console.print(table)

        console.print("\n[green]Budget generated successfully[/green]")
        if output_format in ["markdown", "both"]:
            console.print(
                f"[dim]Narrative: {output_dir / 'budget_narrative.md'}[/dim]"
            )
        if output_format in ["json", "both"]:
            console.print(f"[dim]JSON: {output_dir / 'budget.json'}[/dim]")

    except Exception as e:
        console.print(f"[red]Budget generation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@click.command()
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
    from ..budget.salary_validator import (
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
                    f"[red]Budget YAML not found: {budget_yaml}[/red]"
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
                            console.print(f"[red]{issue}[/red]")
                    if result.warnings:
                        for warning in result.warnings:
                            console.print(f"[yellow]{warning}[/yellow]")
                    if result.suggestions:
                        for suggestion in result.suggestions:
                            console.print(f"[dim]   {suggestion}[/dim]")
                    console.print()

            if not has_issues:
                console.print(
                    "[green]All personnel salaries are within market range[/green]"
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
                    "[green]Salary is within reasonable range[/green]"
                )
            else:
                console.print(
                    "[red]Salary may be flagged by reviewers[/red]"
                )

            for issue in result.issues:
                console.print(f"[red]  - {issue}[/red]")
            for warning in result.warnings:
                console.print(f"[yellow]  - {warning}[/yellow]")
            for suggestion in result.suggestions:
                console.print(f"[dim]  {suggestion}[/dim]")

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
        console.print(f"[red]Salary validation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)

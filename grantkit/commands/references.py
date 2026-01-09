"""Reference and citation commands for GrantKit."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..core.assembler import GrantAssembler
from ..core.validator import NSFValidator
from ..references import BibliographyGenerator, BibTeXManager, CitationExtractor

console = Console()


@click.command()
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

Total Bibliography Entries: {len(bibtex_manager.entries)}
Total Citations Found: {citation_report.total_citations}
Unique Citation Keys: {citation_report.unique_citations}
Missing Bibliography Entries: {len(citation_report.missing_entries)}
Unused Bibliography Entries: {len(citation_report.unused_entries)}
Files with Citations: {len(citation_report.citations_by_file)}"""

        if citation_report.missing_entries or citation_report.unused_entries:
            panel_style = "yellow"
        else:
            panel_style = "green"
            panel_content += "\n\nAll citations properly referenced!"

        console.print(Panel(panel_content, style=panel_style))

        # Show missing entries
        if citation_report.missing_entries and not unused_only:
            console.print(
                f"\n[red]Missing Bibliography Entries ({len(citation_report.missing_entries)}):[/red]"
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
                f"\n[yellow]Unused Bibliography Entries ({len(citation_report.unused_entries)}):[/yellow]"
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
                        f"  - Line {citation.line_number}: {citation.citation_key}"
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
        console.print(f"[red]Citation check failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@click.command()
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
                    "[red]Cannot validate - assembly failed[/red]"
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
                        "[cyan]Using separated document validation[/cyan]"
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
                        "[yellow]Using combined document validation[/yellow]"
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
            console.print("[green]URL and email validation passed![/green]")
        else:
            status_color = (
                "red" if validation_result.errors_count > 0 else "yellow"
            )
            console.print(
                f"[{status_color}]URL/email validation issues found[/{status_color}]"
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
                        "[red]ERROR[/red]"
                        if issue.severity == "error"
                        else "[yellow]WARN[/yellow]" if issue.severity == "warning" else "[blue]INFO[/blue]"
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
                        console.print(f"   [dim]{issue.location}[/dim]")
                    if issue.suggestion:
                        console.print(f"   [dim]{issue.suggestion}[/dim]")
                    if issue.rule:
                        console.print(f"   [dim]{issue.rule}[/dim]")

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
        console.print(f"[red]URL validation failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)

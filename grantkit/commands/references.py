"""Reference and citation commands for GrantKit."""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..core.assembler import GrantAssembler
from ..core.validator import NSFValidator
from ..references import BibliographyGenerator, BibTeXManager, CitationExtractor

console = Console()


def _format_author_year(entry) -> str:
    """Format a bibtex entry as (Author, Year) for inline citation."""
    if not entry:
        return "(Unknown)"

    # Get first author's last name
    if entry.authors:
        first_author = entry.authors[0]
        # Handle "Last, First" format
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            # Handle "First Last" format
            parts = first_author.split()
            last_name = parts[-1] if parts else first_author

        # Handle institutional authors (already full name)
        if last_name.startswith("{") or " " in last_name:
            last_name = last_name.strip("{}")
    else:
        last_name = "Unknown"

    year = entry.year or "n.d."

    # Add "et al." for multiple authors
    if entry.authors and len(entry.authors) > 2:
        return f"({last_name} et al., {year})"
    elif entry.authors and len(entry.authors) == 2:
        # Get second author's last name
        second_author = entry.authors[1]
        if "," in second_author:
            second_last = second_author.split(",")[0].strip()
        else:
            parts = second_author.split()
            second_last = parts[-1] if parts else second_author
        return f"({last_name} & {second_last}, {year})"
    else:
        return f"({last_name}, {year})"


def _format_bibliography_entry(entry, style: str = "apa") -> str:
    """Format a bibtex entry for the bibliography section."""
    if not entry:
        return ""

    # Format authors
    if entry.authors:
        if len(entry.authors) == 1:
            authors_str = entry.authors[0]
        elif len(entry.authors) == 2:
            authors_str = f"{entry.authors[0]} & {entry.authors[1]}"
        else:
            authors_str = ", ".join(entry.authors[:-1]) + f", & {entry.authors[-1]}"
    else:
        authors_str = "Unknown"

    year = entry.year or "n.d."
    title = entry.title or "Untitled"

    # Build citation based on entry type
    entry_type = entry.entry_type.lower()

    if entry_type == "article":
        journal = entry.journal or ""
        volume = entry.volume or ""
        pages = entry.pages or ""

        citation = f"{authors_str} ({year}). {title}."
        if journal:
            citation += f" {journal}"
            if volume:
                citation += f", {volume}"
            if pages:
                citation += f", {pages}"
            citation += "."
    elif entry_type in ("book", "incollection"):
        publisher = entry.raw_entry.get("publisher", "")
        citation = f"{authors_str} ({year}). {title}."
        if publisher:
            citation += f" {publisher}."
    elif entry_type in ("techreport", "misc"):
        institution = entry.raw_entry.get("institution", "")
        url = entry.url or ""
        citation = f"{authors_str} ({year}). {title}."
        if institution:
            citation += f" {institution}."
        if url:
            citation += f" Retrieved from {url}"
    else:
        # Default format
        citation = f"{authors_str} ({year}). {title}."
        if entry.url:
            citation += f" Retrieved from {entry.url}"

    return citation


def _render_citations_in_file(
    content: str, bibtex_manager: BibTeXManager
) -> Tuple[str, List[str], List[str]]:
    """
    Replace [@key] citations with (Author, Year) format.

    Returns:
        Tuple of (rendered_content, used_keys, missing_keys)
    """
    used_keys = []
    missing_keys = []

    # Pattern for pandoc-style citations: [@key] or [@key1; @key2]
    citation_pattern = r"\[@([^\]]+)\]"

    def replace_citation(match):
        citation_text = match.group(1)
        # Handle multiple citations separated by ; or ,
        keys = [k.strip().lstrip("@") for k in re.split(r"[;,]", citation_text)]

        formatted_citations = []
        for key in keys:
            if not key:
                continue

            entry = bibtex_manager.get_entry(key)
            if entry:
                used_keys.append(key)
                formatted_citations.append(_format_author_year(entry))
            else:
                missing_keys.append(key)
                formatted_citations.append(f"([{key}])")

        # Combine multiple citations
        if len(formatted_citations) == 1:
            return formatted_citations[0]
        else:
            # Combine like (Smith, 2020; Jones, 2021)
            inner = "; ".join(c.strip("()") for c in formatted_citations)
            return f"({inner})"

    rendered = re.sub(citation_pattern, replace_citation, content)
    return rendered, list(set(used_keys)), list(set(missing_keys))


@click.command("render-references")
@click.option("--grant", "-g", required=True, help="Grant directory to process")
@click.option("--dry-run", is_flag=True, help="Show what would change without modifying files")
@click.option("--bibliography-file", "-b", help="Output file for bibliography (default: l_bibliographic_references.md)")
@click.pass_context
def render_references(
    ctx: click.Context,
    grant: str,
    dry_run: bool,
    bibliography_file: Optional[str],
) -> None:
    """Render bibtex citations as (Author, Year) and generate bibliography.

    This command:
    1. Finds all [@key] citations in response files
    2. Replaces them with (Author, Year) format using references.bib
    3. Generates the bibliography section

    Example:
        grantkit render-references -g nuffield-rda-2025-full
        grantkit render-references -g nuffield-rda-2025-full --dry-run
    """
    project_root = ctx.obj["project_root"]
    grant_dir = project_root / grant

    if not grant_dir.exists():
        console.print(f"[red]Grant directory not found: {grant_dir}[/red]")
        sys.exit(1)

    # Load bibtex
    bibtex_manager = BibTeXManager(grant_dir)
    bibtex_manager.load_bibliography()

    if not bibtex_manager.entries:
        console.print("[yellow]No bibliography entries found[/yellow]")
        console.print("[dim]Create a references.bib file in the grant directory[/dim]")
        sys.exit(1)

    console.print(f"[green]Loaded {len(bibtex_manager.entries)} bibliography entries[/green]")

    # Find response files
    response_dirs = [
        grant_dir / "responses" / "full",
        grant_dir / "responses",
        grant_dir / "docs" / "responses",
    ]

    responses_dir = None
    for d in response_dirs:
        if d.exists():
            responses_dir = d
            break

    if not responses_dir:
        console.print("[red]No responses directory found[/red]")
        sys.exit(1)

    # Process each file
    all_used_keys = set()
    all_missing_keys = set()
    files_modified = 0

    for md_file in sorted(responses_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")

        # Check if file has citations
        if "[@" not in content:
            continue

        rendered, used_keys, missing_keys = _render_citations_in_file(content, bibtex_manager)
        all_used_keys.update(used_keys)
        all_missing_keys.update(missing_keys)

        if rendered != content:
            files_modified += 1
            console.print(f"[cyan]{md_file.name}[/cyan]: {len(used_keys)} citations rendered")

            if dry_run:
                # Show diff preview
                console.print("[dim]  Would replace:[/dim]")
                for key in used_keys:
                    entry = bibtex_manager.get_entry(key)
                    console.print(f"    [@{key}] → {_format_author_year(entry)}")
            else:
                md_file.write_text(rendered, encoding="utf-8")

    # Report missing keys
    if all_missing_keys:
        console.print(f"\n[red]Missing bibliography entries ({len(all_missing_keys)}):[/red]")
        for key in sorted(all_missing_keys):
            console.print(f"  - {key}")

    # Generate bibliography
    if all_used_keys:
        console.print(f"\n[bold]Generating bibliography ({len(all_used_keys)} entries)...[/bold]")

        # Sort entries alphabetically by first author
        sorted_keys = sorted(
            all_used_keys,
            key=lambda k: (
                bibtex_manager.get_entry(k).authors[0].split(",")[0].lower()
                if bibtex_manager.get_entry(k) and bibtex_manager.get_entry(k).authors
                else k.lower()
            ),
        )

        # Generate bibliography content
        bib_lines = []
        for key in sorted_keys:
            entry = bibtex_manager.get_entry(key)
            if entry:
                bib_lines.append(_format_bibliography_entry(entry))

        bibliography_content = "\n\n".join(bib_lines)

        # Determine output file
        if bibliography_file:
            bib_path = responses_dir / bibliography_file
        else:
            # Look for existing bibliography file in grant.yaml
            grant_yaml = grant_dir / "grant.yaml"
            bib_path = responses_dir / "l_bibliographic_references.md"

            if grant_yaml.exists():
                with open(grant_yaml) as f:
                    grant_meta = yaml.safe_load(f) or {}
                full_app = grant_meta.get("full_application", {})
                sections = full_app.get("sections", grant_meta.get("sections", []))
                for section in sections:
                    if "bibliograph" in section.get("id", "").lower() or "reference" in section.get("id", "").lower():
                        bib_path = grant_dir / section.get("file", "responses/l_bibliographic_references.md")
                        break

        if dry_run:
            console.print(f"\n[dim]Would write bibliography to: {bib_path}[/dim]")
            console.print("[dim]Preview:[/dim]")
            for line in bibliography_content.split("\n\n")[:5]:
                console.print(f"  {line[:100]}...")
            if len(sorted_keys) > 5:
                console.print(f"  ... and {len(sorted_keys) - 5} more entries")
        else:
            bib_path.write_text(bibliography_content, encoding="utf-8")
            console.print(f"[green]Bibliography written to: {bib_path}[/green]")

    # Summary
    console.print()
    if dry_run:
        console.print(f"[yellow]Dry run complete. Would modify {files_modified} files.[/yellow]")
    else:
        console.print(f"[green]Rendered citations in {files_modified} files.[/green]")

    if all_missing_keys:
        sys.exit(1)


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

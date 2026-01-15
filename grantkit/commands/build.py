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
from ..core.markdown_validator import MarkdownContentValidator
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
@click.option("--grant", "-g", help="Specific grant directory to validate")
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.option("--nsf", is_flag=True, help="Run NSF-specific compliance checks")
@click.pass_context
def validate(ctx: click.Context, grant: Optional[str], strict: bool, nsf: bool) -> None:
    """Run comprehensive validation on grant responses.

    Checks:
    - Word/character counts against limits defined in grant.yaml
    - Markdown syntax in plain-text grants (accepts_markdown: false)
    - Missing required sections
    - NSF-specific compliance (with --nsf flag)

    Examples:
        grantkit validate                    # Validate all grants
        grantkit validate -g nuffield-2025   # Validate specific grant
        grantkit validate --nsf              # Include NSF compliance checks
    """
    import yaml

    project_root = ctx.obj["project_root"]
    total_errors = 0
    total_warnings = 0

    # Find grant directories
    if grant:
        grant_dirs = [project_root / grant]
    else:
        grant_dirs = [
            d
            for d in project_root.iterdir()
            if d.is_dir() and (d / "grant.yaml").exists()
        ]

    if not grant_dirs:
        console.print("[yellow]No grants found to validate[/yellow]")
        console.print("[dim]Run from a directory containing grant folders with grant.yaml[/dim]")
        return

    for grant_dir in grant_dirs:
        grant_yaml = grant_dir / "grant.yaml"
        if not grant_yaml.exists():
            continue

        with open(grant_yaml) as f:
            grant_meta = yaml.safe_load(f) or {}

        grant_name = grant_meta.get("name", grant_dir.name)
        console.print(f"\n[bold cyan]Validating: {grant_name}[/bold cyan]")
        console.print(f"[dim]{grant_dir}[/dim]\n")

        grant_errors = 0
        grant_warnings = 0

        # Get sections config - check full_application first (Nuffield-style), then top-level
        full_app = grant_meta.get("full_application", {})
        sections = full_app.get("sections", grant_meta.get("sections", []))
        accepts_markdown = full_app.get(
            "accepts_markdown", grant_meta.get("accepts_markdown", True)
        )

        # === Word Count Validation ===
        console.print("[bold]Word Counts:[/bold]")
        word_count_table = Table(show_header=True, header_style="bold")
        word_count_table.add_column("Section")
        word_count_table.add_column("Words", justify="right")
        word_count_table.add_column("Limit", justify="right")
        word_count_table.add_column("Status")

        for section in sections:
            file_path = grant_dir / section.get("file", f"responses/{section['id']}.md")
            word_limit = section.get("word_limit")
            char_limit = section.get("char_limit")

            if not file_path.exists():
                word_count_table.add_row(
                    section.get("title", section["id"]),
                    "-",
                    str(word_limit) if word_limit else "-",
                    "[red]MISSING[/red]",
                )
                if section.get("required", True):
                    grant_errors += 1
                continue

            content = file_path.read_text(encoding="utf-8")

            # Strip frontmatter for word count
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()

            word_count = len(content.split())

            # Determine status
            if word_limit:
                limit_str = f"{word_limit:,}"
                if word_count > word_limit:
                    over = word_count - word_limit
                    status = f"[red]OVER by {over:,}[/red]"
                    grant_errors += 1
                elif word_count > word_limit * 0.95:
                    remaining = word_limit - word_count
                    status = f"[yellow]{remaining:,} left[/yellow]"
                else:
                    status = "[green]OK[/green]"
            elif char_limit:
                char_count = len(content)
                limit_str = f"{char_limit:,} chars"
                if char_count > char_limit:
                    over = char_count - char_limit
                    status = f"[red]OVER by {over:,} chars[/red]"
                    grant_errors += 1
                else:
                    status = "[green]OK[/green]"
            else:
                limit_str = "-"
                status = "[dim]no limit[/dim]"

            word_count_table.add_row(
                section.get("title", section["id"]),
                f"{word_count:,}",
                limit_str,
                status,
            )

        console.print(word_count_table)

        # === Markdown Syntax Validation ===
        if not accepts_markdown:
            console.print("\n[bold]Markdown Syntax Check:[/bold]")
            console.print("[dim]Grant requires plain text (accepts_markdown: false)[/dim]")

            md_validator = MarkdownContentValidator(accepts_markdown=False)

            # Find responses directory
            response_dirs = [
                grant_dir / "responses" / "full",
                grant_dir / "responses",
                grant_dir / "docs" / "responses",
            ]

            md_errors = []
            for responses_dir in response_dirs:
                if responses_dir.exists():
                    result = md_validator.validate_directory(responses_dir)
                    md_errors = result.violations
                    break

            if md_errors:
                console.print(f"[red]Found {len(md_errors)} markdown syntax issues:[/red]")
                # Group by file
                by_file = {}
                for v in md_errors:
                    if v.file_path not in by_file:
                        by_file[v.file_path] = []
                    by_file[v.file_path].append(v)

                for file_path, violations in list(by_file.items())[:5]:  # Show first 5 files
                    console.print(f"  [bold]{file_path}[/bold]")
                    for v in violations[:3]:  # Show first 3 per file
                        console.print(f"    Line {v.line_number}: [red]{v.message}[/red]")
                    if len(violations) > 3:
                        console.print(f"    [dim]... and {len(violations) - 3} more in this file[/dim]")

                if len(by_file) > 5:
                    console.print(f"  [dim]... and {len(by_file) - 5} more files with issues[/dim]")

                grant_errors += len(md_errors)
            else:
                console.print("[green]No markdown syntax issues found[/green]")
        else:
            console.print("\n[dim]Markdown syntax check skipped (accepts_markdown: true)[/dim]")

        # === NSF-Specific Validation ===
        if nsf:
            console.print("\n[bold]NSF Compliance Check:[/bold]")
            try:
                nsf_validator = NSFValidator(grant_dir)
                nsf_result = nsf_validator.validate()

                if nsf_result.passed:
                    console.print("[green]NSF compliance checks passed[/green]")
                else:
                    console.print(f"[red]Found {nsf_result.errors_count} NSF compliance errors[/red]")
                    for issue in nsf_result.issues[:5]:
                        if issue.severity == "error":
                            console.print(f"  [red]- {issue.message}[/red]")
                    grant_errors += nsf_result.errors_count
                    grant_warnings += nsf_result.warnings_count
            except Exception as e:
                console.print(f"[yellow]NSF validation skipped: {e}[/yellow]")

        # === Grant Summary ===
        console.print()
        if grant_errors == 0 and grant_warnings == 0:
            console.print(f"[green]✓ {grant_dir.name}: All checks passed[/green]")
        elif grant_errors == 0:
            console.print(f"[yellow]⚠ {grant_dir.name}: {grant_warnings} warning(s)[/yellow]")
        else:
            console.print(f"[red]✗ {grant_dir.name}: {grant_errors} error(s), {grant_warnings} warning(s)[/red]")

        total_errors += grant_errors
        total_warnings += grant_warnings

    # === Overall Summary ===
    console.print("\n" + "=" * 50)
    if total_errors == 0 and total_warnings == 0:
        console.print("[bold green]All validation checks passed![/bold green]")
    elif total_errors == 0:
        console.print(f"[bold yellow]Validation complete with {total_warnings} warning(s)[/bold yellow]")
    else:
        console.print(f"[bold red]Validation failed: {total_errors} error(s), {total_warnings} warning(s)[/bold red]")

    if total_errors > 0 or (strict and total_warnings > 0):
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


@click.command("validate-markdown")
@click.option("--grant", "-g", help="Specific grant directory to validate")
@click.pass_context
def validate_markdown(ctx: click.Context, grant: Optional[str]) -> None:
    """Validate that plain-text grants don't contain markdown syntax.

    Checks response files in grants marked with accepts_markdown: false
    for markdown syntax like tables, headers, bold/italic, links, etc.

    This catches issues where markdown formatting would be copied literally
    into a text-only submission form.
    """
    import yaml

    project_root = ctx.obj["project_root"]
    errors = []
    grants_checked = 0

    # Find grant directories
    if grant:
        grant_dirs = [project_root / grant]
    else:
        grant_dirs = [
            d
            for d in project_root.iterdir()
            if d.is_dir() and (d / "grant.yaml").exists()
        ]

    for grant_dir in grant_dirs:
        grant_yaml = grant_dir / "grant.yaml"
        if not grant_yaml.exists():
            continue

        # Check if grant accepts markdown
        with open(grant_yaml) as f:
            grant_meta = yaml.safe_load(f) or {}

        # Check in full_application (Nuffield-style) or top-level
        full_app = grant_meta.get("full_application", {})
        accepts_markdown = full_app.get(
            "accepts_markdown", grant_meta.get("accepts_markdown", True)
        )

        if accepts_markdown:
            console.print(
                f"[dim]{grant_dir.name}: accepts_markdown=true, skipping[/dim]"
            )
            continue

        grants_checked += 1
        console.print(f"[cyan]Checking {grant_dir.name}...[/cyan]")

        # Validate this grant's responses
        validator = MarkdownContentValidator(accepts_markdown=False)

        # Check multiple possible response locations
        response_dirs = [
            grant_dir / "responses" / "full",
            grant_dir / "responses",
            grant_dir / "docs" / "responses",
        ]

        for responses_dir in response_dirs:
            if responses_dir.exists():
                result = validator.validate_directory(responses_dir)
                for violation in result.violations:
                    errors.append(
                        (
                            grant_dir.name,
                            violation.file_path,
                            violation.line_number,
                            violation.message,
                            violation.line_content,
                        )
                    )
                break

    # Report results
    console.print()
    if not grants_checked:
        console.print("[yellow]No plain-text grants found to validate[/yellow]")
        console.print(
            "[dim]Grants with accepts_markdown: true (or unset) are skipped[/dim]"
        )
        return

    if not errors:
        console.print(
            f"[green]All {grants_checked} plain-text grant(s) passed validation![/green]"
        )
        return

    # Show errors grouped by file
    console.print(f"[red]Found {len(errors)} markdown syntax issues:[/red]\n")

    current_file = None
    for grant_name, file_path, line_num, message, line_content in errors:
        file_key = f"{grant_name}/{file_path}"
        if file_key != current_file:
            console.print(f"[bold]{file_key}[/bold]")
            current_file = file_key
        console.print(f"  Line {line_num}: [red]{message}[/red]")
        console.print(f"    [dim]{line_content[:80]}...[/dim]" if len(line_content) > 80 else f"    [dim]{line_content}[/dim]")

    console.print(
        f"\n[yellow]Fix these issues by converting markdown to plain text.[/yellow]"
    )
    sys.exit(1)

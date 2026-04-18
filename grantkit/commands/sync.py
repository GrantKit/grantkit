"""Sync commands for GrantKit (pull, push, watch, share)."""

import difflib
import sys
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..auth import is_logged_in
from ..core.markdown_validator import MarkdownContentValidator
from ..core.validator import NSFValidator
from ..sync_plan import ChangeKind, EntityChange, SyncPlan

console = Console()


_KIND_DISPLAY = {
    ChangeKind.LOCAL_ONLY_ADDED: ("local", "added locally"),
    ChangeKind.LOCAL_ONLY_MODIFIED: ("local", "modified locally"),
    ChangeKind.LOCAL_DELETED: ("local", "deleted locally"),
    ChangeKind.CLOUD_ONLY_ADDED: ("cloud", "new on cloud"),
    ChangeKind.CLOUD_ONLY_MODIFIED: ("cloud", "modified on cloud"),
    ChangeKind.CONFLICT: ("conflict", "changed both sides"),
    ChangeKind.UNCHANGED: ("", ""),
}


def _format_entity(change: EntityChange) -> str:
    if change.entity_type == "grant":
        return f"grant {change.grant_id}"
    if change.entity_type == "response":
        return f"{change.grant_id}/responses/{change.entity_id}.md"
    if change.entity_type == "bibliography_entry":
        return f"{change.grant_id}/references.bib#{change.entity_id}"
    return f"{change.entity_type}:{change.entity_id}"


def _print_plan(plan: SyncPlan) -> None:
    """Render a SyncPlan as a Rich table."""
    if not plan.changes:
        console.print(
            "[green]Nothing to sync - local and cloud agree.[/green]"
        )
        return

    table = Table(title="Sync plan")
    table.add_column("Side", style="cyan")
    table.add_column("Change", style="yellow")
    table.add_column("Entity")
    for change in plan.changes:
        side, label = _KIND_DISPLAY.get(change.kind, ("", change.kind.value))
        style = "red" if change.kind == ChangeKind.CONFLICT else None
        table.add_row(side, label, _format_entity(change), style=style)
    console.print(table)

    counts = {}
    for change in plan.changes:
        counts[change.kind] = counts.get(change.kind, 0) + 1
    summary = ", ".join(
        f"{_KIND_DISPLAY[kind][1]}: {n}"
        for kind, n in counts.items()
        if kind != ChangeKind.UNCHANGED
    )
    if summary:
        console.print(f"[dim]{summary}[/dim]")


@click.group()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Sync grants with Supabase (pull, push, watch)."""
    pass


@sync.command()
@click.option("--grant", "-g", help="Specific grant ID to pull (default: all)")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be pulled without writing any files.",
)
@click.pass_context
def pull(ctx: click.Context, grant: Optional[str], dry_run: bool) -> None:
    """Pull grants and responses from Supabase to local files."""
    from ..sync import get_sync_client

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
            stats = sync_client.pull(grant_id=grant, dry_run=dry_run)

        if dry_run:
            console.print("\n[cyan]Dry run - no files written.[/cyan]")
            _print_plan(stats["plan"])
            return

        console.print("\n[green]Pull complete![/green]")
        console.print(f"   Grants: {stats['grants']}")
        console.print(f"   Responses: {stats['responses']}")
        console.print(f"   Files written: {stats['files_written']}")

    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print(
            "\n[dim]Set GRANTKIT_SUPABASE_KEY environment variable or create grantkit.yaml[/dim]"
        )
        sys.exit(1)
    except ConnectionError as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        console.print(
            "\n[dim]Check your internet connection and Supabase URL[/dim]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Pull failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


def _validate_markdown_content(
    project_root, grant_filter: Optional[str] = None
) -> list:
    """
    Validate markdown content in grants that don't accept markdown.

    Returns list of error messages for violations found.
    """

    import yaml

    errors = []

    # Find grant directories
    if grant_filter:
        grant_dirs = [project_root / grant_filter]
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
            continue  # Skip grants that accept markdown

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
                        f"{grant_dir.name}/{violation.file_path}:{violation.line_number} "
                        f"- {violation.message}"
                    )
                break

    return errors


@sync.command()
@click.option("--grant", "-g", help="Specific grant ID to push (default: all)")
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Run NSF validation before push",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be pushed without touching Supabase.",
)
@click.option(
    "--force",
    is_flag=True,
    help=(
        "Overwrite cloud changes that were made since the last pull. "
        "Use only after reviewing `grantkit sync status`."
    ),
)
@click.option(
    "--regenerate-bibliography/--no-regenerate-bibliography",
    default=None,
    help=(
        "Regenerate the bibliography section from citations. "
        "Default is to regenerate only when the file doesn't exist "
        "yet, to avoid overwriting manual edits."
    ),
)
@click.option(
    "--with-deletes",
    is_flag=True,
    help=(
        "Delete cloud rows for response / bibliography entries that "
        "were in the sync baseline but are no longer on disk. Off by "
        "default to avoid destructive surprises."
    ),
)
@click.pass_context
def push(
    ctx: click.Context,
    grant: Optional[str],
    validate: bool,
    dry_run: bool,
    force: bool,
    regenerate_bibliography: Optional[bool],
    with_deletes: bool,
) -> None:
    """Push local files to Supabase."""
    from ..sync import SyncConflictError, get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        # Optionally validate first
        if validate and not dry_run:
            console.print("[dim]Running validation...[/dim]")

            # Run NSF validation - use grant-specific path if -g flag provided
            validation_root = project_root / grant if grant else project_root
            validator = NSFValidator(validation_root)
            result = validator.validate()

            if not result.passed:
                console.print(
                    f"\n[yellow]Validation found {result.errors_count} errors[/yellow]"
                )
                for issue in result.issues:
                    if issue.severity == "error":
                        console.print(f"   [red]- {issue.message}[/red]")
                if not click.confirm("Continue with push anyway?"):
                    console.print("[red]Push cancelled.[/red]")
                    return

            # Run markdown content validation for grants that don't accept markdown
            markdown_errors = _validate_markdown_content(project_root, grant)
            if markdown_errors:
                console.print(
                    "\n[yellow]Found markdown syntax in plain-text grant(s):[/yellow]"
                )
                for error in markdown_errors[:10]:  # Show first 10
                    console.print(f"   [red]- {error}[/red]")
                if len(markdown_errors) > 10:
                    console.print(
                        f"   [dim]... and {len(markdown_errors) - 10} more[/dim]"
                    )
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
            stats = sync_client.push(
                grant_id=grant,
                force=force,
                dry_run=dry_run,
                regenerate_bibliography=regenerate_bibliography,
                with_deletes=with_deletes,
            )

        if dry_run:
            console.print("\n[cyan]Dry run - nothing pushed.[/cyan]")
            _print_plan(stats["plan"])
            return

        console.print("\n[green]Push complete![/green]")
        console.print(f"   Grants: {stats['grants']}")
        console.print(f"   Responses: {stats['responses']}")
        if stats.get("deleted"):
            console.print(f"   Deleted: {stats['deleted']}")
        if stats.get("bibliography_entries"):
            console.print(
                f"   Bibliography entries: {stats['bibliography_entries']}"
            )
        if stats.get("bibliography_generated"):
            console.print(
                "   [cyan]Bibliography auto-generated from citations[/cyan]"
            )
        if stats.get("bibliography_skipped"):
            for grant_name in stats["bibliography_skipped"]:
                console.print(
                    f"   [yellow]Bibliography regen skipped for "
                    f"{grant_name}[/yellow] "
                    f"[dim](pass --regenerate-bibliography to overwrite)[/dim]"
                )
        if stats.get("deletions_skipped"):
            for entry in stats["deletions_skipped"]:
                console.print(
                    f"   [yellow]Delete skipped:[/yellow] "
                    f"{entry['grant_id']}/{entry['entity']} "
                    f"[dim](pass --with-deletes to remove from cloud)[/dim]"
                )
        if stats.get("grant_yaml_updated_from_budget"):
            for grant_name in stats["grant_yaml_updated_from_budget"]:
                console.print(
                    f"   [yellow]grant.yaml updated from budget.yaml "
                    f"in {grant_name} - commit this change[/yellow]"
                )

        if stats["errors"]:
            console.print(
                f"\n[yellow]{len(stats['errors'])} errors occurred:[/yellow]"
            )
            for error in stats["errors"]:
                console.print(f"   [red]- {error}[/red]")

    except SyncConflictError as e:
        console.print(
            "\n[red]Conflict: cloud has changes that aren't in your "
            "local copy.[/red]"
        )
        _print_plan(e.plan)
        console.print(
            "\n[dim]Resolve with: `grantkit sync pull` to adopt cloud "
            "changes, or re-run with `--force` to overwrite.[/dim]"
        )
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print(
            "\n[dim]Set GRANTKIT_SUPABASE_KEY environment variable or create grantkit.yaml[/dim]"
        )
        sys.exit(1)
    except ConnectionError as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        console.print(
            "\n[dim]Check your internet connection and Supabase URL[/dim]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Push failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@sync.command()
@click.option(
    "--grant", "-g", help="Specific grant ID to check (default: all)"
)
@click.option(
    "--offline",
    is_flag=True,
    help="Only compare against the local sync baseline, skip cloud probe.",
)
@click.pass_context
def status(ctx: click.Context, grant: Optional[str], offline: bool) -> None:
    """Show what differs between local files, cloud, and the last-sync baseline.

    Use this before `push` or `pull` to understand what will happen.
    """
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        sync_client = get_sync_client(project_root)
        plan = sync_client.compute_plan(
            grant_id=grant, include_cloud=not offline
        )
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Status failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)

    _print_plan(plan)
    if plan.has_conflicts:
        sys.exit(2)


def _read_local_response(project_root, grant_id: str, key: str) -> str:
    from pathlib import Path

    grant_dir = Path(project_root) / grant_id
    for responses_dir in (
        grant_dir / "responses" / "full",
        grant_dir / "responses",
        grant_dir / "docs" / "responses",
    ):
        candidate = responses_dir / f"{key}.md"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return ""


def _fetch_cloud_response(client, grant_id: str, key: str) -> str:
    try:
        rows = (
            client.table("responses")
            .select("content")
            .eq("grant_id", grant_id)
            .eq("key", key)
            .execute()
        )
        data = getattr(rows, "data", None)
        if isinstance(data, list) and data:
            return data[0].get("content") or ""
    except Exception:
        return ""
    return ""


def _render_diff(
    title: str, left_label: str, left: str, right_label: str, right: str
) -> None:
    lines = list(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=left_label,
            tofile=right_label,
            n=3,
        )
    )
    if not lines:
        console.print(f"[dim]{title}: no textual difference[/dim]")
        return
    console.print(f"\n[bold]{title}[/bold]")
    for line in lines:
        stripped = line.rstrip("\n")
        if line.startswith("+++") or line.startswith("---"):
            console.print(f"[bold]{stripped}[/bold]")
        elif line.startswith("+"):
            console.print(f"[green]{stripped}[/green]")
        elif line.startswith("-"):
            console.print(f"[red]{stripped}[/red]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{stripped}[/cyan]")
        else:
            console.print(stripped)


@sync.command()
@click.option("--grant", "-g", help="Specific grant ID to diff (default: all)")
@click.pass_context
def diff(ctx: click.Context, grant: Optional[str]) -> None:
    """Show textual diffs for response files that differ between local and cloud.

    Grant metadata and bibliography entries are summarized, not rendered
    as text diffs (they are YAML/bibtex, which diffs poorly by line).
    """
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]
    try:
        sync_client = get_sync_client(project_root)
        plan = sync_client.compute_plan(grant_id=grant, include_cloud=True)
    except Exception as e:
        console.print(f"[red]Diff failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)

    if not plan.changes:
        console.print("[green]No differences.[/green]")
        return

    for change in plan.changes:
        if change.entity_type != "response":
            console.print(
                f"[dim]{_format_entity(change)}: "
                f"{_KIND_DISPLAY[change.kind][1]}[/dim]"
            )
            continue

        title = _format_entity(change)
        local = _read_local_response(
            project_root, change.grant_id, change.entity_id
        )
        if change.kind in (
            ChangeKind.LOCAL_ONLY_ADDED,
            ChangeKind.LOCAL_ONLY_MODIFIED,
        ):
            cloud = _fetch_cloud_response(
                sync_client.client, change.grant_id, change.entity_id
            )
            _render_diff(title, "cloud", cloud, "local", local)
        elif change.kind in (
            ChangeKind.CLOUD_ONLY_ADDED,
            ChangeKind.CLOUD_ONLY_MODIFIED,
        ):
            cloud = _fetch_cloud_response(
                sync_client.client, change.grant_id, change.entity_id
            )
            _render_diff(title, "local", local, "cloud", cloud)
        elif change.kind == ChangeKind.CONFLICT:
            cloud = _fetch_cloud_response(
                sync_client.client, change.grant_id, change.entity_id
            )
            console.print(f"\n[red]CONFLICT: {title}[/red]")
            _render_diff(title, "cloud", cloud, "local", local)


@sync.command()
@click.option(
    "--grant", "-g", help="Specific grant ID to watch (default: all)"
)
@click.pass_context
def watch(ctx: click.Context, grant: Optional[str]) -> None:
    """Watch for file changes and auto-sync to Supabase."""
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        sync_client = get_sync_client(project_root)

        if grant:
            sync_client.config.grant_id = grant

        console.print(f"[green]Watching {project_root} for changes...[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        def on_sync(stats):
            console.print(
                f"[green]Synced[/green] {stats['responses']} responses"
            )

        sync_client.watch(callback=on_sync)

    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print(
            "\n[dim]Set GRANTKIT_SUPABASE_KEY environment variable or create grantkit.yaml[/dim]"
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped.[/yellow]")
    except ConnectionError as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        console.print(
            "\n[dim]Check your internet connection and Supabase URL[/dim]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Watch failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@sync.command()
@click.argument("grant_id")
@click.argument("email")
@click.option(
    "--role",
    "-r",
    type=click.Choice(["viewer", "editor"], case_sensitive=False),
    default="editor",
    help="Permission level (default: editor)",
)
@click.pass_context
def share(ctx: click.Context, grant_id: str, email: str, role: str) -> None:
    """Share a grant with another user.

    GRANT_ID is the grant to share (e.g., 'anthropic-economic-futures').
    EMAIL is the collaborator's email address.

    Examples:
        grantkit sync share my-grant colleague@example.com
        grantkit sync share my-grant colleague@example.com --role viewer
    """
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]

    if not is_logged_in():
        console.print("[red]You must be logged in to share grants[/red]")
        console.print("[dim]Run 'grantkit auth login' first[/dim]")
        sys.exit(1)

    try:
        sync_client = get_sync_client(project_root)
        result = sync_client.share(grant_id=grant_id, email=email, role=role)

        if result["success"]:
            console.print(
                f"[green]Shared '{grant_id}' with {email} as {role}[/green]"
            )
        else:
            console.print(f"[red]{result['error']}[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Share failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@sync.command()
@click.argument("grant_id")
@click.argument("email")
@click.pass_context
def unshare(ctx: click.Context, grant_id: str, email: str) -> None:
    """Remove a collaborator from a grant.

    GRANT_ID is the grant ID.
    EMAIL is the collaborator's email to remove.
    """
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]

    if not is_logged_in():
        console.print(
            "[red]You must be logged in to manage collaborators[/red]"
        )
        console.print("[dim]Run 'grantkit auth login' first[/dim]")
        sys.exit(1)

    try:
        sync_client = get_sync_client(project_root)
        result = sync_client.unshare(grant_id=grant_id, email=email)

        if result["success"]:
            console.print(f"[green]Removed {email} from '{grant_id}'[/green]")
        else:
            console.print(f"[red]{result['error']}[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Unshare failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


@sync.command("collaborators")
@click.argument("grant_id")
@click.pass_context
def list_collaborators(ctx: click.Context, grant_id: str) -> None:
    """List all collaborators for a grant.

    GRANT_ID is the grant to list collaborators for.
    """
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]

    if not is_logged_in():
        console.print("[red]You must be logged in to view collaborators[/red]")
        console.print("[dim]Run 'grantkit auth login' first[/dim]")
        sys.exit(1)

    try:
        sync_client = get_sync_client(project_root)
        result = sync_client.list_collaborators(grant_id=grant_id)

        if not result["success"]:
            console.print(f"[red]{result.get('error', 'Unknown error')}[/red]")
            sys.exit(1)

        collaborators = result.get("collaborators", [])
        if not collaborators:
            console.print(
                f"[yellow]No collaborators found for '{grant_id}'[/yellow]"
            )
            return

        table = Table(title=f"Collaborators for '{grant_id}'")
        table.add_column("Email", style="cyan")
        table.add_column("Role", style="green")
        table.add_column("Added", style="dim")

        for collab in collaborators:
            table.add_row(
                collab["user_email"],
                collab["role"],
                (
                    collab.get("created_at", "")[:10]
                    if collab.get("created_at")
                    else ""
                ),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to list collaborators: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)

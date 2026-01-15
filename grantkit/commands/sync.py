"""Sync commands for GrantKit (pull, push, watch, share)."""

import sys
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..auth import is_logged_in
from ..core.validator import NSFValidator

console = Console()


@click.group()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Sync grants with Supabase (pull, push, watch)."""
    pass


@sync.command()
@click.option("--grant", "-g", help="Specific grant ID to pull (default: all)")
@click.pass_context
def pull(ctx: click.Context, grant: Optional[str]) -> None:
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
            stats = sync_client.pull(grant_id=grant)

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
    except Exception as e:
        console.print(f"[red]Pull failed: {e}[/red]")
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
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        # Optionally validate first
        if validate:
            console.print("[dim]Running validation...[/dim]")
            validator = NSFValidator(project_root)
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

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Connecting to Supabase...", total=None)

            sync_client = get_sync_client(project_root)

            progress.update(task, description="Pushing to Supabase...")
            stats = sync_client.push(grant_id=grant)

        console.print("\n[green]Push complete![/green]")
        console.print(f"   Grants: {stats['grants']}")
        console.print(f"   Responses: {stats['responses']}")

        if stats["errors"]:
            console.print(
                f"\n[yellow]{len(stats['errors'])} errors occurred:[/yellow]"
            )
            for error in stats["errors"]:
                console.print(f"   [red]- {error}[/red]")

    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print(
            "\n[dim]Set GRANTKIT_SUPABASE_KEY environment variable or create grantkit.yaml[/dim]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Push failed: {e}[/red]")
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
    from ..sync import get_sync_client

    project_root = ctx.obj["project_root"]

    try:
        sync_client = get_sync_client(project_root)

        if grant:
            sync_client.config.grant_id = grant

        console.print(
            f"[green]Watching {project_root} for changes...[/green]"
        )
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
            console.print(
                f"[green]Removed {email} from '{grant_id}'[/green]"
            )
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
        console.print(
            "[red]You must be logged in to view collaborators[/red]"
        )
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

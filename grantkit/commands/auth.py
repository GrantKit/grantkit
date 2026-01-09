"""Authentication commands for GrantKit."""

import sys

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..auth import (
    clear_credentials,
    device_login,
    get_current_user,
    is_logged_in,
)

console = Console()


@click.group()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Manage authentication (login, logout, status)."""
    pass


@auth.command()
@click.pass_context
def login(ctx: click.Context) -> None:
    """Login to GrantKit via browser (OAuth device flow)."""
    if is_logged_in():
        user = get_current_user()
        console.print(f"[yellow]Already logged in as {user}[/yellow]")
        if not click.confirm("Login again?"):
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Opening browser...", total=None)

        creds = device_login()

        if creds:
            progress.update(task, description="Login successful!")
            console.print(
                f"\n[green]Logged in as {creds.user_email}[/green]"
            )
        else:
            console.print("\n[red]Login failed[/red]")
            sys.exit(1)


@auth.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Logout and clear stored credentials."""
    if not is_logged_in():
        console.print("[yellow]Not currently logged in[/yellow]")
        return

    user = get_current_user()
    clear_credentials()
    console.print(f"[green]Logged out from {user}[/green]")


@auth.command()
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Show current authentication status."""
    if is_logged_in():
        user = get_current_user()
        console.print(f"[green]Logged in as {user}[/green]")
    else:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("[dim]Run 'grantkit auth login' to authenticate[/dim]")

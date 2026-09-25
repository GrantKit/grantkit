"""GrantKit command-line interface.

Six verbs, one engine:

* ``grantkit init``   — scaffold a grant project (optionally from a funder pack)
* ``grantkit check``  — lint the proposal (the linter)
* ``grantkit build``  — compile responses into one document (the compiler)
* ``grantkit review`` — emit a review packet for an AI agent
* ``grantkit status`` — completion, word counts, deadline countdown
* ``grantkit budget`` — compile a portfolio selection into a budget

The engine is stateless and local-first: it reads files, writes files, and
makes no network or AI calls (except opt-in link checking under
``check --urls`` and opt-in BLS/GSA lookups when those API keys are set).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional, cast

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__
from .core.builder import BuildDependencyError, build_project
from .core.checks import CheckResult, run_checks
from .core.project import GrantProject, GrantProjectError
from .core.review import build_review
from .core.scaffold import ScaffoldError, init_project
from .core.status import build_status, days_until_deadline, write_status
from .menu import (
    compile_combined,
    run_combined_gates,
    run_gates,
    selection_cost,
)
from .menu.loader import Portfolio, PortfolioError, load_portfolio
from .menu.model import model_bundle
from .menu.render import (
    budget_json,
    budget_markdown,
    combined_budget_json,
    combined_budget_markdown,
    print_budget,
)
from .menu.schema import Selection
from .packs import FunderPack

console = Console()
err_console = Console(stderr=True)

PATH_ARG = click.argument(
    "path",
    type=click.Path(file_okay=False, path_type=Path),
    default=".",
    required=False,
)


def _terminal_text(value: object, *, style: Optional[str] = None) -> Text:
    """Build Rich text that remains encodable for hostile YAML strings."""
    safe = str(value).encode("utf-8", "backslashreplace").decode("utf-8")
    escaped: list[str] = []
    for char in safe:
        codepoint = ord(char)
        if char in "\n\t" or not (codepoint < 32 or 0x7F <= codepoint <= 0x9F):
            escaped.append(char)
        elif codepoint <= 0xFF:
            escaped.append(f"\\x{codepoint:02x}")
        else:  # pragma: no cover - C1 controls are all <= 0xff
            escaped.append(f"\\u{codepoint:04x}")
    payload = "".join(escaped)
    return Text(payload, style=style) if style is not None else Text(payload)


def _load_project(path: Path) -> GrantProject:
    grant_yaml = Path(path) / "grant.yaml"
    if not grant_yaml.exists():
        err_console.print(
            f"[red]No grant.yaml found in {Path(path).resolve()}[/red]\n"
            "Run [bold]grantkit init[/bold] to scaffold one."
        )
        raise SystemExit(2)
    try:
        return GrantProject(Path(path))
    except GrantProjectError as exc:
        err_console.print(_terminal_text(exc, style="red"))
        raise SystemExit(2)


@click.group()
@click.version_option(__version__, prog_name="grantkit")
def main() -> None:
    """GrantKit — the linter and compiler for grant proposals."""


# -- init ---------------------------------------------------------------


@main.command()
@click.option(
    "--funder",
    "funder",
    default=None,
    help="Funder rule-pack id (e.g. nsf-pappg, nuffield-rda, pbif).",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite an existing grant.yaml / budget.yaml.",
)
@PATH_ARG
def init(funder: Optional[str], force: bool, path: Path) -> None:
    """Scaffold a new grant project."""
    try:
        created = init_project(Path(path), funder=funder, force=force)
    except ScaffoldError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise SystemExit(2)

    console.print(
        f"[green]Initialized grant project in {Path(path).resolve()}[/green]"
    )
    for file_path in created:
        try:
            rel = file_path.relative_to(Path(path).resolve())
        except ValueError:
            rel = file_path
        console.print(f"  [dim]created[/dim] {rel}")
    if funder:
        console.print(
            f"\nUsing funder pack [bold]{funder}[/bold]. "
            "Edit responses/, then run [bold]grantkit check[/bold]."
        )
    else:
        console.print(
            "\nEdit grant.yaml + responses/, then run "
            "[bold]grantkit check[/bold]."
        )


# -- check --------------------------------------------------------------


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.option("--strict", is_flag=True, help="Treat warnings as failures too.")
@click.option(
    "--urls",
    "check_urls",
    is_flag=True,
    help="Also check that URLs are reachable (makes network requests).",
)
@PATH_ARG
def check(as_json: bool, strict: bool, check_urls: bool, path: Path) -> None:
    """Lint the proposal; exit non-zero on errors (or warnings with --strict)."""
    project = _load_project(path)
    result = run_checks(project, strict=strict, check_urls=check_urls)

    if as_json:
        # Raw stdout so CI / agents capture clean JSON.
        sys.stdout.write(json.dumps(result.to_dict(), indent=2) + "\n")
    else:
        _print_checks(result)

    raise SystemExit(1 if result.failed(strict=strict) else 0)


def _print_checks(result: CheckResult) -> None:
    if not result.items:
        console.print("[green]All checks passed.[/green]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Level")
    table.add_column("Rule")
    table.add_column("Section")
    table.add_column("Message")
    for item in result.items:
        color = "red" if item.level == "error" else "yellow"
        table.add_row(
            _terminal_text(item.level, style=color),
            _terminal_text(item.rule),
            _terminal_text(item.section or "-"),
            _terminal_text(item.message),
        )
    console.print(table)
    console.print(
        f"\n[bold]{result.errors}[/bold] error(s), "
        f"[bold]{result.warnings}[/bold] warning(s)."
    )


# -- build --------------------------------------------------------------


@main.command()
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "html", "pdf", "docx"]),
    default="md",
    help=(
        "Output format for the compiled review document; NSF PDFs are "
        "review-only."
    ),
)
@click.option(
    "--share",
    is_flag=True,
    help="Also write a self-contained assembled.html review page.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path for the compiled document (default proposal.<format>).",
)
@PATH_ARG
def build(fmt: str, share: bool, output: Optional[Path], path: Path) -> None:
    """Assemble responses into one review document and refresh status.json."""
    project = _load_project(path)
    try:
        result = build_project(project, fmt=fmt, share=share, output=output)
    except BuildDependencyError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise SystemExit(2)

    console.print("[green]Build complete.[/green]")
    for out in result.outputs():
        try:
            rel = out.relative_to(Path(path).resolve())
        except ValueError:
            rel = out
        console.print(f"  [dim]wrote[/dim] {rel}")
    for warning in result.warnings:
        err_console.print(
            Text.assemble(
                ("warning", "yellow"),
                " ",
                _terminal_text(warning),
            )
        )


# -- review -------------------------------------------------------------


@main.command()
@click.option(
    "--pack",
    "include_pack",
    is_flag=True,
    help="Embed the full funder rule pack, not just the rubric.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the packet to a file instead of stdout.",
)
@PATH_ARG
def review(include_pack: bool, output: Optional[Path], path: Path) -> None:
    """Emit a structured review packet for an AI agent (no AI calls)."""
    project = _load_project(path)
    packet = build_review(project, include_pack=include_pack)
    payload = json.dumps(packet, indent=2) + "\n"
    if output:
        Path(output).write_text(payload, encoding="utf-8")
        console.print(f"[green]Wrote review packet to {output}[/green]")
    else:
        # Raw stdout so the packet pipes cleanly into an agent.
        sys.stdout.write(payload)


# -- status -------------------------------------------------------------


@main.command()
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Write status.json (and print it).",
)
@PATH_ARG
def status(as_json: bool, path: Path) -> None:
    """Show completion %, per-section word counts, and deadline countdown."""
    project = _load_project(path)

    if as_json:
        write_status(project)
        payload = build_status(project)
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return

    _print_status(project)


def _print_status(project: GrantProject) -> None:
    console.print(f"[bold]{project.title or project.funder or 'Grant'}[/bold]")
    if project.program:
        console.print(f"[dim]{project.program}[/dim]")

    countdown = days_until_deadline(project.deadline)
    if project.deadline:
        if countdown is None:
            when = project.deadline
        elif countdown < 0:
            when = f"{project.deadline} ({abs(countdown)} days ago)"
        else:
            when = f"{project.deadline} (in {countdown} days)"
        console.print(f"Deadline: {when}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Section")
    table.add_column("Words", justify="right")
    table.add_column("Limit", justify="right")
    table.add_column("Status")
    for section in project.sections:
        badge = {
            "complete": "[green]complete[/green]",
            "partial": "[yellow]partial[/yellow]",
            "empty": "[dim]empty[/dim]",
            "over_limit": "[red]over limit[/red]",
        }.get(section.status, section.status)
        table.add_row(
            section.title,
            str(section.words),
            str(section.word_limit or "-"),
            badge,
        )
    console.print(table)
    console.print(
        f"\n[bold]{project.completion_percent:.0f}%[/bold] complete — "
        f"{project.sections_complete}/{project.sections_total} sections, "
        f"{project.total_words:,} words."
    )


# -- budget -------------------------------------------------------------


def _parse_combine_ids(value: str) -> list[str]:
    """Parse the comma-separated combine option into canonical ids."""
    parts = value.split(",")
    ids = [part.strip() for part in parts]
    if any(not selection_id for selection_id in ids):
        raise click.UsageError(
            "--combine must be a comma-separated list of selection ids"
        )
    if len(ids) < 2:
        raise click.UsageError("--combine requires at least two selections")
    if len(set(ids)) != len(ids):
        raise click.UsageError("--combine cannot repeat a selection id")
    return sorted(ids)


@main.command()
@click.option(
    "--selection",
    "selection_id",
    default=None,
    help=(
        "Selection id to compile, or to scope --check. Required to compile "
        "a multi-selection portfolio unless a grant project binds one."
    ),
)
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help=(
        "Run the integrity gates only; exit 1 on errors (2 on selection, "
        "configuration, or loading failures)."
    ),
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit the full structured compilation (or gate findings) as JSON.",
)
@click.option(
    "--all",
    "all_selections",
    is_flag=True,
    help="Compile every selection; requires --json.",
)
@click.option(
    "--combine",
    default=None,
    metavar="ID1,ID2[,...]",
    help=(
        "Roll up two or more selections as one live funding scenario; "
        "requires --json and/or --output."
    ),
)
@click.option(
    "--export-model",
    "export_model",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the normalized grantkit-model/v1 bundle.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the markdown budget document to a file.",
)
@click.option(
    "--narrative",
    is_flag=True,
    help=(
        "Include the narrative skeleton in the markdown output (without "
        "--output, prints the markdown document to stdout)."
    ),
)
@click.option(
    "--periods",
    "show_periods",
    is_flag=True,
    help="Include phasing and staffing tables in rich/Markdown output.",
)
@PATH_ARG
def budget(
    selection_id: Optional[str],
    check_only: bool,
    as_json: bool,
    all_selections: bool,
    combine: Optional[str],
    export_model: Optional[Path],
    output: Optional[Path],
    narrative: bool,
    show_periods: bool,
    path: Path,
) -> None:
    """Compile a portfolio selection into a budget (menu x rates).

    PATH is a portfolio directory (menu.yaml + rates.yaml + selections/)
    or a grant project whose grant.yaml binds one via a budget_model block.
    """
    combine_ids = _parse_combine_ids(combine) if combine is not None else None
    if check_only and output is not None:
        raise click.UsageError("--output cannot be used with --check")
    if check_only and narrative:
        raise click.UsageError("--narrative cannot be used with --check")
    if check_only and show_periods:
        raise click.UsageError("--periods cannot be used with --check")
    if as_json and narrative and output is None:
        raise click.UsageError(
            "--narrative with --json requires --output for the markdown"
        )
    if all_selections and not as_json:
        raise click.UsageError("--all requires --json")
    if all_selections and selection_id is not None:
        raise click.UsageError("--selection cannot be used with --all")
    if all_selections and check_only:
        raise click.UsageError("--check cannot be used with --all")
    if all_selections and output is not None:
        raise click.UsageError("--output cannot be used with --all")
    if all_selections and narrative:
        raise click.UsageError("--narrative cannot be used with --all")
    if combine_ids is not None and selection_id is not None:
        raise click.UsageError("--selection cannot be used with --combine")
    if combine_ids is not None and all_selections:
        raise click.UsageError("--all cannot be used with --combine")
    if combine_ids is not None and check_only:
        raise click.UsageError("--check cannot be used with --combine")
    if combine_ids is not None and narrative:
        raise click.UsageError("--narrative cannot be used with --combine")
    if combine_ids is not None and show_periods:
        raise click.UsageError("--periods cannot be used with --combine")
    if (
        combine_ids is not None
        and not as_json
        and output is None
        and export_model is None
    ):
        raise click.UsageError("--combine requires --json and/or --output")
    if export_model is not None:
        conflicts = [
            (selection_id is not None, "--selection"),
            (all_selections, "--all"),
            (check_only, "--check"),
            (as_json, "--json"),
            (output is not None, "--output"),
            (narrative, "--narrative"),
            (show_periods, "--periods"),
            (combine_ids is not None, "--combine"),
        ]
        for active, option in conflicts:
            if active:
                raise click.UsageError(
                    f"{option} cannot be used with --export-model"
                )

    portfolio, selection_id, pack = _load_portfolio_target(
        path,
        selection_id,
        resolve_bound_selection=not (
            all_selections
            or combine_ids is not None
            or export_model is not None
        ),
    )

    if export_model is not None:
        result = CheckResult(items=run_gates(portfolio))
        if result.errors:
            _print_checks(result)
            err_console.print(
                "[red]Cannot export: fix the reported errors.[/red]"
            )
            raise SystemExit(1)
        _emit_budget_warnings(result)
        payload = (
            json.dumps(
                model_bundle(portfolio),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
        try:
            Path(export_model).write_text(payload, encoding="utf-8")
        except OSError as exc:
            err_console.print(
                _terminal_text(
                    f"Could not write model bundle to {export_model}: {exc}",
                    style="red",
                )
            )
            raise SystemExit(2)
        console.print(
            _terminal_text(
                f"Wrote model bundle to {export_model}", style="green"
            )
        )
        return

    if combine_ids is not None:
        for combined_id in combine_ids:
            _resolve_selection(portfolio, combined_id)
        result = CheckResult(items=run_combined_gates(portfolio, combine_ids))
        blocking_errors = [
            item
            for item in result.items
            if item.level == "error"
            and item.rule != "cofunding_over_allocated"
        ]
        if blocking_errors:
            if as_json:
                sys.stdout.write(
                    json.dumps(
                        result.to_dict(),
                        indent=2,
                        sort_keys=True,
                        allow_nan=False,
                    )
                    + "\n"
                )
            else:
                _print_checks(result)
            err_console.print(
                "[red]Cannot compile: fix the reported structural errors "
                "(or run budget --check).[/red]"
            )
            raise SystemExit(1)

        combined = compile_combined(portfolio, combine_ids)
        if output is not None:
            markdown = combined_budget_markdown(portfolio, combined, result)
            try:
                Path(output).write_text(markdown, encoding="utf-8")
            except OSError as exc:
                err_console.print(
                    _terminal_text(
                        f"Could not write budget document to {output}: {exc}",
                        style="red",
                    )
                )
                raise SystemExit(2)
            destination = err_console if as_json else console
            destination.print(
                _terminal_text(
                    f"Wrote budget document to {output}", style="green"
                )
            )
        if as_json:
            sys.stdout.write(
                json.dumps(
                    combined_budget_json(portfolio, combined, result),
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            )
        return

    if all_selections:
        result = CheckResult(items=run_gates(portfolio, None, pack))
        if result.errors:
            sys.stdout.write(
                json.dumps(
                    result.to_dict(), indent=2, sort_keys=True, allow_nan=False
                )
                + "\n"
            )
            err_console.print(
                "[red]Cannot compile: fix the reported errors (or run "
                "budget --check).[/red]"
            )
            raise SystemExit(1)
        _emit_budget_warnings(result)
        compiled = {
            selection.id: budget_json(
                portfolio, selection, selection_cost(selection, portfolio)
            )
            for selection in sorted(
                portfolio.selections, key=lambda item: item.id
            )
        }
        sys.stdout.write(
            json.dumps(
                {"selections": compiled},
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
        return

    if check_only:
        if selection_id is not None:
            _resolve_selection(portfolio, selection_id)
        result = CheckResult(items=run_gates(portfolio, selection_id, pack))
        if as_json:
            sys.stdout.write(
                json.dumps(result.to_dict(), indent=2, allow_nan=False) + "\n"
            )
        else:
            _print_checks(result)
        raise SystemExit(1 if result.failed() else 0)

    selection = _resolve_selection(portfolio, selection_id)
    result = CheckResult(items=run_gates(portfolio, selection.id, pack))
    if result.errors:
        if as_json:
            sys.stdout.write(
                json.dumps(result.to_dict(), indent=2, allow_nan=False) + "\n"
            )
        else:
            _print_checks(result)
        err_console.print(
            "[red]Cannot compile: fix the reported errors (or run "
            "budget --check).[/red]"
        )
        raise SystemExit(1)
    _emit_budget_warnings(result)

    cost = selection_cost(selection, portfolio)
    if output:
        payload = budget_markdown(
            portfolio,
            selection,
            cost,
            narrative=narrative,
            periods=show_periods,
        )
        try:
            Path(output).write_text(payload, encoding="utf-8")
        except OSError as exc:
            err_console.print(
                _terminal_text(
                    f"Could not write budget document to {output}: {exc}",
                    style="red",
                )
            )
            raise SystemExit(2)
        destination = err_console if as_json else console
        destination.print(
            _terminal_text(f"Wrote budget document to {output}", style="green")
        )
    if as_json:
        payload_json = budget_json(portfolio, selection, cost)
        sys.stdout.write(
            json.dumps(payload_json, indent=2, allow_nan=False) + "\n"
        )
    elif narrative and not output:
        sys.stdout.write(
            budget_markdown(
                portfolio,
                selection,
                cost,
                narrative=True,
                periods=show_periods,
            )
        )
    elif not output:
        print_budget(console, portfolio, selection, cost, periods=show_periods)


def _emit_budget_warnings(result: CheckResult) -> None:
    for item in result.items:
        if item.level != "warning":
            continue
        err_console.print(
            Text.assemble(
                ("warning", "yellow"),
                " ",
                _terminal_text(item.rule),
                ": ",
                _terminal_text(item.message),
            )
        )


def _load_portfolio_target(
    path: Path,
    selection_id: Optional[str],
    *,
    resolve_bound_selection: bool = True,
) -> tuple[Portfolio, Optional[str], Optional[FunderPack]]:
    """Resolve PATH to (portfolio, selection id, pack).

    PATH may be a portfolio directory or a grant project bound to one
    via ``budget_model:``. Exits 2 when neither is readable.
    """
    pack = None
    portfolio_dir = Path(path)
    bound_project = False
    if (Path(path) / "grant.yaml").exists():
        bound_project = True
        project = _load_project(Path(path))
        binding = project.budget_model
        portfolio_value = binding.get("portfolio") if binding else None
        if not isinstance(portfolio_value, str) or not portfolio_value:
            err_console.print(
                _terminal_text(
                    f"{project.grant_yaml_path} has no valid budget_model "
                    "portfolio binding.\nAdd one:\n\n"
                    "  budget_model:\n"
                    "    portfolio: ../org-portfolio\n"
                    "    selection: my-proposal\n\n"
                    "or point grantkit budget at a portfolio directory.",
                    style="red",
                )
            )
            raise SystemExit(2)
        try:
            portfolio_dir = (project.root / portfolio_value).resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            err_console.print(
                _terminal_text(
                    f"Could not resolve the bound portfolio: {exc}",
                    style="red",
                )
            )
            raise SystemExit(2)
        assert binding is not None
        if selection_id is None:
            bound = binding.get("selection")
            if bound is not None and not isinstance(bound, str):
                err_console.print(
                    _terminal_text(
                        "budget_model.selection must be a string id.",
                        style="red",
                    )
                )
                raise SystemExit(2)
            selection_id = bound
        pack = project.pack
    try:
        portfolio = load_portfolio(portfolio_dir)
    except PortfolioError as exc:
        err_console.print(_terminal_text(exc, style="red"))
        raise SystemExit(2)
    if bound_project and selection_id is None and resolve_bound_selection:
        selection_id = _resolve_selection(portfolio, None).id
    return portfolio, selection_id, pack


def _resolve_selection(
    portfolio: Portfolio, selection_id: Optional[str]
) -> Selection:
    """Pick the selection to compile; exits 2 when ambiguous/unknown."""
    if selection_id is None:
        if not portfolio.selections:
            err_console.print(
                "[red]This portfolio has no selections.[/red]\n"
                "Add selections/*.yaml, or add a single selection.yaml "
                "beside menu.yaml."
            )
            raise SystemExit(2)
        if len(portfolio.selections) == 1:
            return cast(Selection, portfolio.selections[0])
        available = ", ".join(portfolio.selection_ids) or "(none)"
        err_console.print(
            _terminal_text(
                "This portfolio has "
                f"{len(portfolio.selections)} selections; pass "
                f"--selection ID.\nAvailable: {available}",
                style="red",
            )
        )
        raise SystemExit(2)
    selection = portfolio.get_selection(selection_id)
    if selection is None:
        available = ", ".join(portfolio.selection_ids) or "(none)"
        err_console.print(
            _terminal_text(
                f"No selection '{selection_id}' in this portfolio.\n"
                f"Available: {available}",
                style="red",
            )
        )
        raise SystemExit(2)
    return cast(Selection, selection)


if __name__ == "__main__":  # pragma: no cover
    main()

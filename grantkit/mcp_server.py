"""GrantKit MCP server.

Exposes the engine as Model Context Protocol tools so an AI agent can lint,
report on, and compile a grant directly. Built on the official ``mcp`` Python
SDK (FastMCP). Install with the ``mcp`` extra and run the ``grantkit-mcp``
console script (stdio transport)::

    pip install "grantkit[mcp]"
    grantkit-mcp

Every tool takes a filesystem ``path`` to a grant project (a directory
containing ``grant.yaml``) and returns the same JSON structures the CLI emits.
No AI or network calls are made (URL/BLS/GSA checks stay off here).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_IMPORT_ERROR: Exception | None = None
try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - optional dependency
    FastMCP = None  # type: ignore[assignment,misc]
    _IMPORT_ERROR = exc


def _load(path: str):
    from .core.project import GrantProject

    root = Path(path).expanduser()
    if not (root / "grant.yaml").exists():
        raise FileNotFoundError(
            f"No grant.yaml in {root.resolve()} — not a grant project."
        )
    return GrantProject(root)


def build_server() -> "FastMCP":
    """Construct and return the configured FastMCP server."""
    if FastMCP is None:  # pragma: no cover - optional dependency
        raise ImportError(
            "The MCP SDK is not installed. Install it with "
            f"`pip install 'grantkit[mcp]'`. Underlying error: {_IMPORT_ERROR}"
        )

    server = FastMCP("grantkit")

    @server.tool()
    def grant_check(path: str = ".") -> dict[str, Any]:
        """Lint the grant project at ``path``.

        Returns ``{"errors", "warnings", "items": [...]}`` where each item is
        ``{"level", "rule", "message", "section", "citation"}``.
        """
        from .core.checks import run_checks

        return run_checks(_load(path)).to_dict()

    @server.tool()
    def grant_status(path: str = ".") -> dict[str, Any]:
        """Return the full status.json document for the grant at ``path``."""
        from .core.status import build_status

        return build_status(_load(path))

    @server.tool()
    def grant_build(path: str = ".", format: str = "md") -> dict[str, Any]:
        """Compile the grant at ``path`` into ``format`` (md/html/pdf/docx).

        Writes the document, a status.json, and returns the output paths plus
        the status document.
        """
        from .core.builder import build_project
        from .core.status import build_status

        project = _load(path)
        result = build_project(project, fmt=format)
        return {
            "format": result.format,
            "outputs": [str(p) for p in result.outputs()],
            "status": build_status(project),
        }

    return server


def main() -> None:
    """Console-script entry point (``grantkit-mcp``)."""
    if FastMCP is None:  # pragma: no cover - optional dependency
        raise SystemExit(
            "The MCP SDK is not installed. Install it with "
            "`pip install 'grantkit[mcp]'`."
        )
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()

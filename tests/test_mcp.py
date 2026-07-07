"""Tests for the MCP server (skipped when the mcp SDK is absent)."""

import asyncio

import pytest

from grantkit import __version__

pytest.importorskip("mcp")

from grantkit.core.scaffold import init_project  # noqa: E402
from grantkit.mcp_server import build_server  # noqa: E402


def test_server_registers_three_tools():
    server = build_server()
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == {"grant_check", "grant_status", "grant_build"}


def test_grant_status_tool_runs(tmp_path):
    init_project(tmp_path, funder="nuffield-rda")
    server = build_server()
    result = asyncio.run(
        server.call_tool("grant_status", {"path": str(tmp_path)})
    )
    # FastMCP returns (content, structured) across versions; the structured
    # payload (a dict) is what we assert on.
    structured = _structured(result)
    assert structured["grantkit_version"] == __version__
    assert "checks" in structured


def _structured(result):
    # Newer FastMCP: (list[Content], structured_result). Older: list[Content].
    if isinstance(result, tuple):
        return result[1]
    raise AssertionError(f"unexpected call_tool result: {type(result)}")

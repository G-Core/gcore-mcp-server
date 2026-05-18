"""Tests for ``register_meta_tools`` — wires three meta-tools onto a FastMCP server."""

from __future__ import annotations

from unittest.mock import Mock

from gcore_mcp_server.code_exec.catalog import Catalog
from gcore_mcp_server.code_exec.meta_tools import register_meta_tools


def test_register_meta_tools_registers_three_tools():
    """``register_meta_tools`` calls ``mcp.add_tool`` exactly three times with the
    expected names and a callable function for each."""
    mcp = Mock()
    catalog = Catalog([])
    client = Mock()

    register_meta_tools(mcp, catalog, client)

    assert mcp.add_tool.call_count == 3

    registered_tools = [c.args[0] for c in mcp.add_tool.call_args_list]
    names = [getattr(t, "name", None) for t in registered_tools]
    assert set(names) == {"search_tools", "get_tool_schema", "execute_code"}

    # Each registered Tool wraps a callable (``Tool.from_function`` requires one).
    for tool in registered_tools:
        # FastMCP Tool exposes its callable as `.fn` (most versions) or via .from_function.
        fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
        assert callable(fn), f"registered tool {tool!r} has no callable fn"

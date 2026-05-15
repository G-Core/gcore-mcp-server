"""Register the three code-execution-mode meta-tools on a FastMCP server."""

from __future__ import annotations

from typing import Any

from fastmcp.tools.tool import Tool  # type: ignore[import-not-found]

from .catalog import Catalog
from .runner import execute_code as _execute_code


_SEARCH_DESC = (
    "Search the Gcore SDK catalog by keyword. Returns top matches with name, "
    "summary, and project/region requirements."
)

_SCHEMA_DESC = "Get the full parameter schema and docs for one tool."

_EXEC_DESC = (
    "Run a short Python script in an embedded Pydantic Monty sandbox to "
    "orchestrate one or more Gcore SDK calls.\n\n"
    "Sandbox capabilities: async/await, list/dict/set comprehensions, "
    "exceptions, and the stdlib modules json, re, and datetime.\n"
    "Not supported: 'class', 'with', 'import', 'match', and generator "
    "functions/expressions.\n\n"
    "Inside the sandbox the following are available without imports:\n"
    "  - await call_tool('cloud.instances.list', project_id=..., region_id=...)\n"
    "  - search_tools(query, limit=20)\n"
    "  - get_tool_schema(name)\n\n"
    "project_id and region_id are pre-resolved when configured on the server, "
    "so call_tool() auto-injects them; otherwise resolve them yourself via "
    "cloud.projects.list / cloud.regions.list."
)


def register_meta_tools(mcp: Any, catalog: Catalog, client: Any) -> None:
    """Add ``search_tools``, ``get_tool_schema`` and ``execute_code`` to ``mcp``."""

    async def search_tools(query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search the Gcore SDK catalog by keyword."""
        return catalog.search(query, limit=limit)

    async def get_tool_schema(name: str) -> dict[str, Any]:
        """Return the parameter schema and docs for one Gcore SDK tool."""
        return catalog.get_schema(name)

    async def execute_code(code: str, timeout_secs: float = 30.0) -> dict[str, Any]:
        """Run a short Python script in the embedded sandbox."""
        result = await _execute_code(code, catalog, client, timeout_secs=timeout_secs)
        return result.to_dict()

    mcp.add_tool(
        Tool.from_function(
            search_tools,
            name="search_tools",
            description=_SEARCH_DESC,
        )
    )
    mcp.add_tool(
        Tool.from_function(
            get_tool_schema,
            name="get_tool_schema",
            description=_SCHEMA_DESC,
        )
    )
    mcp.add_tool(
        Tool.from_function(
            execute_code,
            name="execute_code",
            description=_EXEC_DESC,
        )
    )

"""Direct mode: one MCP tool per selected SDK method."""

from __future__ import annotations

import hashlib
import inspect
import logging
from typing import Annotated, Any

from fastmcp import Context
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from pydantic import Field

from gcore_mcp_server.catalog import Access, ToolEntry
from gcore_mcp_server.runtime import Dispatcher
from gcore_mcp_server.runtime.safety import InputNeeded
from gcore_mcp_server.runtime.shaping import text_result

logger = logging.getLogger(__name__)

MAX_TOOL_NAME = 64
MAX_DESCRIPTION = 1200


def tool_name_for(entry: ToolEntry) -> str:
    """MCP-safe tool identifier: the dotted SDK path with underscores."""
    name = entry.tool_name
    if len(name) > MAX_TOOL_NAME:
        # No SDK path is this long today; keep names unique and legal if one is.
        digest = hashlib.sha1(entry.name.encode()).hexdigest()[:8]
        name = f"{name[: MAX_TOOL_NAME - 9]}_{digest}"
    return name


def annotations_for(entry: ToolEntry) -> ToolAnnotations:
    return ToolAnnotations(
        title=entry.summary[:80] or entry.name,
        read_only_hint=entry.access is Access.READ,
        destructive_hint=entry.access is Access.DESTRUCTIVE,
        open_world_hint=True,
    )


def build_direct_tool(entry: ToolEntry, dispatcher: Dispatcher) -> Tool:
    """Wrap ``entry`` as a FastMCP tool that dispatches through ``dispatcher``."""
    policy = dispatcher.policy
    base = inspect.signature(entry.fn)
    params = list(base.parameters.values())
    annotations: dict[str, Any] = {p.name: p.annotation for p in params}

    if policy.needs_confirmation(entry):
        ann = Annotated[
            str | None, Field(description="Only when a previous response asked for it.")
        ]
        params.append(
            inspect.Parameter(
                "confirm_token",
                inspect.Parameter.KEYWORD_ONLY,
                default=None,
                annotation=ann,
            )
        )
        annotations["confirm_token"] = ann
    params.append(
        inspect.Parameter(
            "ctx",
            inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=Context | None,
        )
    )
    annotations["ctx"] = Context | None
    annotations["return"] = Any

    async def tool_fn(**kwargs: Any) -> Any:
        ctx = kwargs.pop("ctx", None)
        token = kwargs.pop("confirm_token", None)
        args = {k: v for k, v in kwargs.items() if v is not None}
        try:
            return text_result(await dispatcher.call(entry, args, ctx, token))
        except InputNeeded as need:
            return need.result

    name = tool_name_for(entry)
    tool_fn.__name__ = name
    tool_fn.__annotations__ = annotations
    tool_fn.__signature__ = inspect.Signature(params, return_annotation=Any)  # type: ignore[attr-defined]

    description = entry.description
    if len(description) > MAX_DESCRIPTION:
        description = description[:MAX_DESCRIPTION] + "…"
    if entry.access is Access.DESTRUCTIVE:
        description = f"[DESTRUCTIVE] {description}"
    return Tool.from_function(
        tool_fn,
        name=name,
        description=description,
        annotations=annotations_for(entry),
        output_schema=None,
    )


def register_direct_tools(
    mcp: Any, entries: list[ToolEntry], dispatcher: Dispatcher
) -> list[str]:
    """Register ``entries`` as tools, skipping ones the policy blocks outright."""
    names: list[str] = []
    for entry in entries:
        if dispatcher.policy.blocked_reason(entry):
            continue  # read-only / denied: don't spend tokens advertising it
        try:
            tool = build_direct_tool(entry, dispatcher)
        except Exception as exc:
            logger.error("Could not register %s: %s", entry.name, exc)
            continue
        mcp.add_tool(tool)
        names.append(tool.name)
    return names

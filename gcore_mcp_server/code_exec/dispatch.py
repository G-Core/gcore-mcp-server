"""Host-side ``call_tool`` dispatcher used from inside the Monty sandbox."""

from __future__ import annotations

import inspect as _inspect
from typing import Any, Awaitable, Callable

from gcore_mcp_server.core.serialize import serialize_result
from gcore_mcp_server.domain import (
    PROJECT_ID_REQUIRED_ERROR,
    REGION_ID_REQUIRED_ERROR,
)

from .catalog import Catalog


def make_call_tool(
    catalog: Catalog,
    client: Any,
) -> Callable[..., Awaitable[Any]]:
    """Return an async ``call_tool(tool_name, /, **kwargs)`` for the sandbox.

    ``tool_name`` is positional-only so that SDK methods which themselves take
    a ``name`` parameter (e.g. ``cloud.ssh_keys.create``) can still be invoked
    as ``call_tool('cloud.ssh_keys.create', name='my-key')`` without the
    keyword colliding with the dispatcher's own first parameter.

    The dispatcher:
      * looks up the SDK method by full or short name,
      * auto-injects ``project_id``/``region_id`` from the configured client
        when the SDK method needs them and the caller did not provide them,
      * awaits the result if it is awaitable,
      * serializes the result via the shared ``serialize_result`` helper so
        Pydantic models are reduced to primitives before crossing into the
        sandbox.
    """

    async def call_tool(tool_name: str, /, **kwargs: Any) -> Any:
        entry = catalog.by_name.get(tool_name)
        if entry is None:
            raise KeyError(
                f"unknown tool: {tool_name!r}. Try search_tools(query) to discover."
            )

        if entry.requires_project and "project_id" not in kwargs:
            if client.cloud_project_id is None:
                raise ValueError(PROJECT_ID_REQUIRED_ERROR)
            kwargs["project_id"] = client.cloud_project_id

        if entry.requires_region and "region_id" not in kwargs:
            if client.cloud_region_id is None:
                raise ValueError(REGION_ID_REQUIRED_ERROR)
            kwargs["region_id"] = client.cloud_region_id

        method = entry.method
        if method is None:
            raise RuntimeError(
                f"catalog entry for {tool_name!r} has no underlying method"
            )

        result = method(**kwargs)
        if _inspect.isawaitable(result):
            result = await result
        return serialize_result(result)

    return call_tool

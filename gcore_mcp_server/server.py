# server_fastmcp.py
"""
Gcore API → Model-Context-Protocol bridge (FastMCP v2)
-------------------------------------------------------------
• Dynamically inspects the public SDK, auto-wraps every method and exposes it
  as an MCP *tool*.
• Tool visibility is restricted via *tool-sets* configured in the environment
  variable `GCORE_TOOLS` (comma-separated list).  Helper logic lives in
  `gcore_mcp_server.config`.
• The server runs in two transport modes, selected through `GCORE_TRANSPORT`:
    – "stdio" (default) …… basic stdio transport (ideal for local LLMs)
    – "http"/"stream" …… streamable HTTP transport (suitable for remote)
  In HTTP mode the *management* tool-set is enabled by default unless
  `GCORE_TOOLS` is provided explicitly.
• OAuth2/JWT will be added later.  `AuthSettings` is left commented for future
  wiring.

Requires `fastmcp>=2.2` and the official «gcore» Python SDK.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
from typing import Any, Callable
from functools import wraps
from fastmcp import FastMCP  # type: ignore[import-not-found]  # FastMCP ≥ 2.7.1
from fastmcp.tools.tool import Tool  # type: ignore[import-not-found]
from gcore import Gcore
from gcore_mcp_server.core.inspection import iter_sdk_methods
from gcore_mcp_server.config.settings import (
    UNIFIED_TOOLS_ENV_VAR,
    generate_short_tool_name,
)
from gcore_mcp_server.config.toolsets import get_allowed_tools_list
from gcore_mcp_server.domain import get_gcore_domain_handler

logger = logging.getLogger("gcore-mcp")
logging.basicConfig(level="INFO", format="%(levelname)s | %(message)s")

# MCP Server Configuration
MCP_NAME = "gcore-api"
MCP_INSTRUCTIONS = "This server provides access to Gcore API"

###############################################################################
# Build a FastMCP wrapper around an SDK method
###############################################################################


def _serialize_result(result: Any) -> Any:  # noqa: ANN401
    """Convert SDK result to JSON-serializable format."""
    if result is None:
        return None

    # Handle basic types
    if isinstance(result, (str, int, float, bool)):
        return result

    # Handle lists
    if isinstance(result, list):
        return [_serialize_result(item) for item in result]  # type: ignore[misc]

    # Handle dicts
    if isinstance(result, dict):
        return {key: _serialize_result(value) for key, value in result.items()}  # type: ignore[misc]

    # Handle objects with model_dump() method (Pydantic v2)
    if hasattr(result, "model_dump") and callable(getattr(result, "model_dump")):
        try:
            return _serialize_result(result.model_dump())
        except Exception:
            pass

    # Handle objects with __dict__
    if hasattr(result, "__dict__"):
        try:
            obj_dict: dict[str, Any] = {}
            for key, value in result.__dict__.items():
                if not key.startswith("_"):  # Skip private attributes
                    obj_dict[key] = _serialize_result(value)
            return obj_dict
        except Exception:
            pass

    # Fallback to string representation
    return str(result)


def make_wrapper(method: Callable[..., Any], full_name: str) -> Callable[..., Any]:
    """Create an **async** function that proxies to *method* keeping its signature."""

    sig = inspect.signature(method)

    @wraps(method)
    async def async_wrapper(**kwargs: Any) -> Any:  # noqa: ANN401 – dynamic
        # Filter out None values for optional parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        # Automatic JSON→object conversion for domain-specific parameters
        domain_handler = get_gcore_domain_handler()
        json_conversion_params = domain_handler.get_json_conversion_parameters()
        
        for key in json_conversion_params:
            if key in filtered_kwargs and isinstance(filtered_kwargs[key], str):
                try:
                    filtered_kwargs[key] = json.loads(filtered_kwargs[key])
                except json.JSONDecodeError:
                    logger.warning("Could not JSON-decode %s for %s", key, full_name)

        result = method(**filtered_kwargs)
        if inspect.isawaitable(result):
            result = await result

        # Serialize the result to ensure JSON compatibility
        return _serialize_result(result)

    # Create proper annotations for FastMCP based on original signature
    simple_annotations: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        # Check if parameter has a default value (making it optional)
        if param.default is not inspect.Parameter.empty:
            # Optional parameter - allow str or None
            simple_annotations[param_name] = str | None
        else:
            # Required parameter
            simple_annotations[param_name] = str
    simple_annotations["return"] = Any
    async_wrapper.__annotations__ = simple_annotations  # type: ignore[attr-defined]

    async_wrapper.__doc__ = method.__doc__ or f"Proxy for `{full_name}`"
    return async_wrapper


###############################################################################
# Environment – transport & tool-sets
###############################################################################

_transport_raw = os.getenv("GCORE_TRANSPORT", "stdio").lower()

# Map aliases → canonical FastMCP transport names
_TRANSPORT_MAP: dict[str, str] = {
    "stdio": "stdio",
    "http": "streamable-http",
    "stream": "streamable-http",
    "streamable-http": "streamable-http",
    "sse": "sse",
}

TRANSPORT: str = _TRANSPORT_MAP.get(_transport_raw, "stdio")
if _transport_raw not in _TRANSPORT_MAP:
    logger.warning(
        "Unknown GCORE_TRANSPORT '%s', falling back to 'stdio'", _transport_raw
    )

# In HTTP mode enable *management* tools by default (unless explicitly set).
if TRANSPORT != "stdio" and not os.getenv(UNIFIED_TOOLS_ENV_VAR):
    os.environ[UNIFIED_TOOLS_ENV_VAR] = "management"

# Get all available tools from SDK for unified tool selection
mcp: Any = FastMCP(name=MCP_NAME, instructions=MCP_INSTRUCTIONS)
client = Gcore()

all_full_tool_names = [full_name for full_name, _ in iter_sdk_methods(client)]

# Use unified tool selection approach
ALLOWED_TOOLS_SHORT: set[str] = set(get_allowed_tools_list(all_full_tool_names))
logger.info("Unified tools config → %s", os.getenv(UNIFIED_TOOLS_ENV_VAR, "<default>"))
logger.info("Total allowed tools: %d", len(ALLOWED_TOOLS_SHORT))

###############################################################################
# Build the FastMCP application
###############################################################################

registered = 0
for full_name, method in iter_sdk_methods(client):
    short_name = generate_short_tool_name(full_name)
    if short_name not in ALLOWED_TOOLS_SHORT:
        continue  # not enabled for this run

    wrapper = make_wrapper(method, full_name)
    tool_name = short_name.replace(".", "_")  # client-facing identifier
    wrapper.__name__ = tool_name  # consistent naming

    tool = Tool.from_function(wrapper, name=tool_name, description=wrapper.__doc__)
    mcp.add_tool(tool)
    registered += 1

logger.info("Registered %d tools", registered)

###############################################################################
# Run
###############################################################################


def main() -> None:
    """Entry point for console script."""
    if TRANSPORT == "stdio":
        mcp.run()
    else:
        port = int(os.getenv("GCORE_PORT", "8000"))
        mcp.run(
            transport=TRANSPORT,
            port=port,
            log_level="INFO",
        )  # type: ignore[arg-type]


if __name__ == "__main__":
    main()

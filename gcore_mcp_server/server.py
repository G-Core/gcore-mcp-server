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
from typing import get_type_hints, get_args, Union as TypingUnion
from gcore import Gcore
import gcore
from gcore_mcp_server.core.inspection import iter_sdk_methods
from gcore_mcp_server.core.schema import normalize_sdk_type_for_mcp
from gcore_mcp_server.core.serialize import serialize_result
from gcore_mcp_server.config.settings import (
    UNIFIED_TOOLS_ENV_VAR,
    ROUTING_CODE_EXEC,
    generate_short_tool_name,
    get_routing_mode,
)
from gcore_mcp_server.config.toolsets import get_allowed_tools_list
from gcore_mcp_server.code_exec import build_catalog, register_meta_tools
from gcore_mcp_server.domain import (
    MCP_PROJECT_REGION_INSTRUCTIONS,
    PROJECT_ID_TOOL_NOTE,
    REGION_ID_TOOL_NOTE,
    PROJECT_ID_REQUIRED_ERROR,
    REGION_ID_REQUIRED_ERROR,
    PROJECT_REGION_LOOKUP_TOOLS,
)

logger = logging.getLogger("gcore-mcp")
logging.basicConfig(level="INFO", format="%(levelname)s | %(message)s")

# MCP Server Configuration
MCP_NAME = "gcore-api"

CODE_EXEC_INSTRUCTIONS_PREAMBLE = (
    "This server runs in code-execution mode. Only three meta-tools are "
    "exposed: search_tools(query), get_tool_schema(name), and "
    "execute_code(code). Call execute_code with a short Python script that "
    "uses `await call_tool('cloud.<resource>.<method>', ...)` to invoke any "
    "of the ~700 Gcore SDK methods. Inside the sandbox you also have "
    "search_tools() and get_tool_schema() as functions. The sandbox supports "
    "async/await, comprehensions, exceptions, and stdlib json/re/datetime; "
    "it does NOT support class, with, import, match, or generators.\n\n"
)


def _build_instructions(routing_mode: str) -> str:
    if routing_mode == ROUTING_CODE_EXEC:
        return CODE_EXEC_INSTRUCTIONS_PREAMBLE + MCP_PROJECT_REGION_INSTRUCTIONS
    return MCP_PROJECT_REGION_INSTRUCTIONS


###############################################################################
# Build a FastMCP wrapper around an SDK method
###############################################################################


def _strip_optional(annotation: Any) -> Any:
    """Remove Optional[...]/Union[..., None] from a type annotation."""
    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))  # noqa: E721
    if not args:
        return annotation
    if len(args) == 1:
        return args[0]
    try:
        return TypingUnion.__getitem__(args)
    except TypeError:
        result = args[0]
        for arg in args[1:]:
            try:
                result = result | arg  # type: ignore[operator]
            except TypeError:
                return annotation
        return result


def make_wrapper(
    method: Callable[..., Any],
    full_name: str,
    require_project_param: bool,
    require_region_param: bool,
) -> Callable[..., Any]:
    """Create an async wrapper that preserves SDK type information for FastMCP."""
    from gcore import NotGiven, Omit

    try:
        sig = inspect.signature(method)
    except Exception as e:
        logger.error("Failed to get signature for %s: %s", full_name, e)
        raise

    @wraps(method)
    async def async_wrapper(**kwargs: Any) -> Any:  # noqa: ANN401 – dynamic
        # Filter out None values for optional parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if (
            require_project_param
            and has_project_param
            and "project_id" not in filtered_kwargs
        ):
            raise ValueError(PROJECT_ID_REQUIRED_ERROR)
        if (
            require_region_param
            and has_region_param
            and "region_id" not in filtered_kwargs
        ):
            raise ValueError(REGION_ID_REQUIRED_ERROR)

        # Backward compatibility: JSON string → object conversion
        # This allows clients to still pass JSON strings if needed
        for key in filtered_kwargs:
            if isinstance(filtered_kwargs[key], str):
                try:
                    filtered_kwargs[key] = json.loads(filtered_kwargs[key])
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON

        result = method(**filtered_kwargs)
        if inspect.isawaitable(result):
            result = await result

        # Serialize the result to ensure JSON compatibility
        return serialize_result(result)

    # Preserve type annotations by normalizing SDK types to FastMCP-compatible types
    try:
        type_hints = get_type_hints(method)
    except Exception as e:
        logger.warning("Failed to get type hints for %s: %s", full_name, e)
        # If type hints fail, fallback to signature annotations
        type_hints = {}
        for param_name, param in sig.parameters.items():
            if param.annotation is not inspect.Parameter.empty:
                type_hints[param_name] = param.annotation

    normalized_annotations: dict[str, Any] = {}

    # Track SDK-specific default values to replace
    sdk_default_types = (NotGiven, Omit)
    try:
        from gcore import Timeout

        sdk_default_types = (NotGiven, Omit, Timeout)
    except ImportError:
        pass

    try:
        for param_name, param in sig.parameters.items():
            if param_name in type_hints:
                # Normalize SDK types (Union[T, NotGiven] → T | None, Iterable[T] → List[T])
                param_type = type_hints[param_name]
                normalized_type = normalize_sdk_type_for_mcp(param_type)
                normalized_annotations[param_name] = normalized_type
            elif param.default is not inspect.Parameter.empty:
                # Has default but no type hint - make optional Any
                normalized_annotations[param_name] = Any | None
            else:
                # Required but no type hint - use Any
                normalized_annotations[param_name] = Any
    except Exception as e:
        logger.error("Failed to normalize annotations for %s: %s", full_name, e)
        raise

    has_project_param = "project_id" in normalized_annotations
    has_region_param = "region_id" in normalized_annotations

    if require_project_param and has_project_param:
        normalized_annotations["project_id"] = _strip_optional(
            normalized_annotations["project_id"]
        )
    if require_region_param and has_region_param:
        normalized_annotations["region_id"] = _strip_optional(
            normalized_annotations["region_id"]
        )

    normalized_annotations["return"] = Any
    async_wrapper.__annotations__ = normalized_annotations  # type: ignore[attr-defined]
    async_wrapper.__doc__ = method.__doc__ or f"Proxy for `{full_name}`"

    # Replace SDK-specific default values with None to avoid Pydantic warnings
    # This creates a new signature with JSON-serializable defaults
    try:
        new_params = []
        for param_name, param in sig.parameters.items():
            if param.default is not inspect.Parameter.empty:
                # Check if default is an SDK-specific type
                if isinstance(param.default, sdk_default_types) or type(
                    param.default
                ).__name__ in ("NotGiven", "Omit", "Timeout"):
                    # Replace with None
                    new_param = param.replace(default=None)
                    new_params.append(new_param)
                else:
                    new_params.append(param)
            else:
                new_params.append(param)

        updated_params = []
        for param in new_params:
            if (
                require_project_param
                and has_project_param
                and param.name == "project_id"
                and param.default is None
            ):
                updated_params.append(param.replace(default=inspect.Parameter.empty))
            elif (
                require_region_param
                and has_region_param
                and param.name == "region_id"
                and param.default is None
            ):
                updated_params.append(param.replace(default=inspect.Parameter.empty))
            else:
                updated_params.append(param)

        # Update wrapper's signature with JSON-serializable defaults
        async_wrapper.__signature__ = sig.replace(parameters=updated_params)  # type: ignore[attr-defined]
    except Exception as e:
        logger.error("Failed to update signature for %s: %s", full_name, e)
        raise

    note_parts: list[str] = []
    if require_project_param and has_project_param:
        note_parts.append(PROJECT_ID_TOOL_NOTE)
    if require_region_param and has_region_param:
        note_parts.append(REGION_ID_TOOL_NOTE)
    if note_parts:
        note = " ".join(note_parts)
        if async_wrapper.__doc__:
            async_wrapper.__doc__ = f"{async_wrapper.__doc__}\n\nNote: {note}"
        else:
            async_wrapper.__doc__ = f"Note: {note}"

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

ROUTING_MODE = get_routing_mode()

# In HTTP mode enable *management* tools by default (unless explicitly set).
# Only applies to `direct` routing — the code_exec mode ignores GCORE_TOOLS.
if (
    TRANSPORT != "stdio"
    and ROUTING_MODE != ROUTING_CODE_EXEC
    and not os.getenv(UNIFIED_TOOLS_ENV_VAR)
):
    os.environ[UNIFIED_TOOLS_ENV_VAR] = "management"

mcp: Any = FastMCP(name=MCP_NAME, instructions=_build_instructions(ROUTING_MODE))
client = Gcore()

# Log Gcore SDK version
gcore_version = getattr(gcore, "__version__", "unknown")
logger.info("Gcore SDK version: %s", gcore_version)
logger.info("Routing mode: %s", ROUTING_MODE)

###############################################################################
# Build the FastMCP application
###############################################################################

if ROUTING_MODE == ROUTING_CODE_EXEC:
    if os.getenv(UNIFIED_TOOLS_ENV_VAR):
        logger.info(
            "GCORE_TOOLS is set but ignored in code_exec mode — the catalog "
            "is searched dynamically from inside execute_code()."
        )
    catalog = build_catalog(client)
    register_meta_tools(mcp, catalog, client)
    logger.info(
        "Registered 3 meta-tools (search_tools, get_tool_schema, execute_code) "
        "over %d SDK methods. Set GCORE_MCP_ROUTING=direct to restore the "
        "legacy tool surface.",
        len(catalog.entries),
    )
else:
    # Legacy direct mode: register each SDK method as its own MCP tool.
    enforce_project_param = client.cloud_project_id is None
    enforce_region_param = client.cloud_region_id is None

    all_full_tool_names = [full_name for full_name, _ in iter_sdk_methods(client)]

    # Use unified tool selection approach
    ALLOWED_TOOLS_SHORT: set[str] = set(get_allowed_tools_list(all_full_tool_names))

    required_lookup_short = {
        generate_short_tool_name(tool_name) for tool_name in PROJECT_REGION_LOOKUP_TOOLS
    }
    ALLOWED_TOOLS_SHORT.update(required_lookup_short)
    logger.info(
        "Ensuring project/region lookup tools are available: %s",
        sorted(required_lookup_short),
    )
    logger.info(
        "Unified tools config → %s", os.getenv(UNIFIED_TOOLS_ENV_VAR, "<default>")
    )
    logger.info("Total allowed tools: %d", len(ALLOWED_TOOLS_SHORT))

    # Track which allowed tools actually exist as SDK methods
    registered = 0
    registered_short_names: set[str] = set()
    failed_registrations: list[tuple[str, str]] = []  # (full_name, error)

    for full_name, method in iter_sdk_methods(client):
        short_name = generate_short_tool_name(full_name)
        if short_name not in ALLOWED_TOOLS_SHORT:
            continue  # not enabled for this run

        try:
            wrapper = make_wrapper(
                method, full_name, enforce_project_param, enforce_region_param
            )
            tool_name = short_name.replace(".", "_")  # client-facing identifier
            wrapper.__name__ = tool_name  # consistent naming

            tool = Tool.from_function(
                wrapper, name=tool_name, description=wrapper.__doc__
            )
            mcp.add_tool(tool)
            registered += 1
            registered_short_names.add(short_name)
        except Exception as e:
            logger.error("Failed to register tool %s: %s", full_name, e)
            failed_registrations.append((full_name, str(e)))

    logger.info("Registered %d tools", registered)

    # Check for allowed tools that don't exist as SDK methods
    missing_tools = ALLOWED_TOOLS_SHORT - registered_short_names
    if missing_tools:
        logger.warning(
            "Tools in allowed list but not found in SDK (%d): %s",
            len(missing_tools),
            sorted(missing_tools),
        )

    if failed_registrations:
        logger.error(
            "Failed to register %d tools: %s",
            len(failed_registrations),
            failed_registrations,
        )

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

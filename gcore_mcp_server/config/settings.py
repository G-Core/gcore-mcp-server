"""Environment settings: GCORE_TOOLS, transport and HTTP allow-lists."""

import os
import logging
from typing import Final

logger = logging.getLogger(__name__)

UNIFIED_TOOLS_ENV_VAR: Final[str] = "GCORE_TOOLS"
ALLOWED_HOSTS_ENV_VAR: Final[str] = "GCORE_ALLOWED_HOSTS"
ALLOWED_ORIGINS_ENV_VAR: Final[str] = "GCORE_ALLOWED_ORIGINS"


TRANSPORT_ENV_VAR: Final[str] = "GCORE_TRANSPORT"

# Map aliases → canonical FastMCP transport names.
TRANSPORT_MAP: Final[dict[str, str]] = {
    "stdio": "stdio",
    "http": "streamable-http",
    "stream": "streamable-http",
    "streamable-http": "streamable-http",
}

# Transports this server refuses to run, with the reason shown to the operator.
# SSE is rejected rather than merely unmapped so it cannot silently fall back
# to stdio. The MCP specification deprecated it in favour of streamable HTTP,
# which is the only HTTP transport this server supports and tests.
UNSUPPORTED_TRANSPORTS: Final[dict[str, str]] = {
    "sse": (
        "the SSE transport is not supported (deprecated by the MCP "
        "specification). Use GCORE_TRANSPORT=http instead."
    ),
}


def resolve_transport(raw: str | None) -> str:
    """Resolve a GCORE_TRANSPORT value to a canonical FastMCP transport name.

    Unknown values fall back to "stdio" with a warning. Values listed in
    UNSUPPORTED_TRANSPORTS raise ValueError so the process fails to start.
    """
    value = (raw or "stdio").strip().lower()
    if value in UNSUPPORTED_TRANSPORTS:
        raise ValueError(f"GCORE_TRANSPORT={value!r}: {UNSUPPORTED_TRANSPORTS[value]}")
    if value not in TRANSPORT_MAP:
        logger.warning("Unknown GCORE_TRANSPORT '%s', falling back to 'stdio'", value)
        return "stdio"
    return TRANSPORT_MAP[value]


def env_flag(name: str, default: bool = False) -> bool:
    """A boolean environment variable; unset or blank means ``default``.

    Anything else that isn't a recognised true/false spelling stops the
    server: a typo (``GCORE_READ_ONLY=treu``) must not silently turn a safe
    default off.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(
        f"{name}={raw!r} is not a boolean; use one of: "
        + ", ".join(sorted(_TRUE | _FALSE))
    )


_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def split_list(raw: str | None) -> list[str]:
    """Comma-separated items, trimmed, without empty ones."""
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def get_allow_list(env_var: str) -> list[str]:
    """Read a comma-separated allow-list from the environment.

    Unset, empty and whitespace-only values all yield an empty list. The list
    is always passed to FastMCP explicitly: passing None would make it fall
    back to its own FASTMCP_HTTP_ALLOWED_* settings, a second configuration
    channel the README does not document.
    """
    return split_list(os.getenv(env_var))

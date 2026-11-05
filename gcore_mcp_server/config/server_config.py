"""Server configuration read from environment variables."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum

from gcore_mcp_server.catalog import Catalog, ToolEntry, matches_any

from .settings import UNIFIED_TOOLS_ENV_VAR, env_flag, split_list

logger = logging.getLogger(__name__)

MODE_ENV_VAR = "GCORE_MCP_MODE"
LEGACY_MODE_ENV_VAR = "GCORE_MCP_ROUTING"  # older spelling, still accepted


class Mode(str, Enum):
    DYNAMIC = "dynamic"
    """A few meta-tools (search, schema, call, code) over the whole SDK. Default."""

    DIRECT = "direct"
    """One MCP tool per SDK method matched by the GCORE_TOOLS patterns."""


_MODE_ALIASES: dict[str, Mode] = {
    "dynamic": Mode.DYNAMIC,
    "search": Mode.DYNAMIC,
    "code": Mode.DYNAMIC,
    "code_exec": Mode.DYNAMIC,
    "direct": Mode.DIRECT,
    "tools": Mode.DIRECT,
}
# Modes that no longer exist, with what replaces them.
_REMOVED_MODES = {"hybrid": Mode.DYNAMIC}

# Always reachable, so a model can resolve project and region IDs.
LOOKUP_TOOLS = (
    "cloud.projects.list",
    "cloud.projects.get",
    "cloud.regions.list",
    "cloud.regions.get",
)


@dataclass
class ServerConfig:
    mode: Mode = Mode.DYNAMIC
    tools: str | None = None
    """Raw GCORE_TOOLS: comma-separated glob patterns over SDK paths."""

    code_execution: bool = True
    code_writes: bool = False
    """Let execute_code scripts change resources (GCORE_CODE_WRITES)."""
    max_result_chars: int = 40_000
    code_timeout_secs: float = 55.0
    """Wall time per execute_code script (GCORE_CODE_TIMEOUT)."""
    wait_secs: float | None = 50.0
    """How long a *_and_poll call waits for its task (GCORE_WAIT_TIMEOUT);
    None (0 in the environment) waits until it is done."""
    notes: list[str] = field(default_factory=list[str])

    @classmethod
    def from_env(cls) -> "ServerConfig":
        notes: list[str] = []
        tools = (os.getenv(UNIFIED_TOOLS_ENV_VAR) or "").strip() or None
        raw_mode = (
            (os.getenv(MODE_ENV_VAR) or os.getenv(LEGACY_MODE_ENV_VAR) or "")
            .strip()
            .lower()
        )
        if raw_mode:
            mode = _MODE_ALIASES.get(raw_mode)
            if raw_mode in _REMOVED_MODES:
                mode = _REMOVED_MODES[raw_mode]
                notes.append(
                    f"{MODE_ENV_VAR}={raw_mode!r} was removed; using "
                    f"{mode.value!r}. Use 'direct' with GCORE_TOOLS for plain tools."
                )
            elif mode is None:
                notes.append(f"Unknown {MODE_ENV_VAR}={raw_mode!r}; using 'dynamic'.")
                mode = Mode.DYNAMIC
        elif tools:
            # Backward compatibility: GCORE_TOOLS alone keeps the classic
            # one-tool-per-method behaviour existing configurations expect.
            mode = Mode.DIRECT
            notes.append(
                "GCORE_TOOLS is set without GCORE_MCP_MODE: using direct mode. "
                "Set GCORE_MCP_MODE=dynamic to change this."
            )
        else:
            mode = Mode.DYNAMIC
        try:
            max_chars = int(os.getenv("GCORE_MAX_RESULT_CHARS") or 40_000)
        except ValueError:
            notes.append("GCORE_MAX_RESULT_CHARS is not a number; using 40000.")
            max_chars = 40_000
        code_timeout = 55.0
        raw_timeout = (os.getenv("GCORE_CODE_TIMEOUT") or "").strip()
        if raw_timeout:
            try:
                code_timeout = float(raw_timeout)
                if code_timeout <= 0:
                    raise ValueError
            except ValueError:
                notes.append(
                    "GCORE_CODE_TIMEOUT must be a positive number of seconds; using 55."
                )
                code_timeout = 55.0
        wait: float | None = 50.0
        raw_wait = (os.getenv("GCORE_WAIT_TIMEOUT") or "").strip()
        if raw_wait:
            try:
                wait = float(raw_wait)
                if wait < 0:
                    raise ValueError
                wait = wait or None
            except ValueError:
                notes.append(
                    "GCORE_WAIT_TIMEOUT must be a number of seconds (0: no limit); "
                    "using 50."
                )
                wait = 50.0
        return cls(
            mode=mode,
            tools=tools,
            code_execution=env_flag("GCORE_CODE_EXECUTION", True),
            code_writes=env_flag("GCORE_CODE_WRITES", False),
            max_result_chars=max_chars,
            code_timeout_secs=code_timeout,
            wait_secs=wait,
            notes=notes,
        )


def parse_patterns(tools: str | None) -> list[str]:
    """GCORE_TOOLS as a list of glob patterns."""
    return split_list(tools)


def select_entries(catalog: Catalog, tools: str | None) -> list[ToolEntry]:
    """Entries matched by the GCORE_TOOLS patterns, plus project/region lookups.

    Patterns match the dotted SDK path: ``cloud.instances.*``, ``dns.zones``
    (a name without a wildcard also matches everything below it). A pattern
    that matches nothing is logged, since it is usually a typo or a name from
    an older version of this server.
    """
    patterns = parse_patterns(tools)
    for pattern in patterns:
        if not any(matches_any(e.name, [pattern]) for e in catalog.entries):
            logger.warning(
                "GCORE_TOOLS pattern %r matches no operation. Patterns match SDK "
                "paths such as 'cloud.instances.*'; toolset names like "
                "'instances' are no longer supported.",
                pattern,
            )
    return [
        e
        for e in catalog.entries
        if e.name in LOOKUP_TOOLS or (patterns and matches_any(e.name, patterns))
    ]


def has_selection(catalog: Catalog, tools: str | None) -> bool:
    """Whether GCORE_TOOLS matches any operation (lookups included).

    A selection of only lookups (``cloud.projects.list``) is valid and must be
    honoured: treating it as empty would fall back to the whole API.
    """
    patterns = parse_patterns(tools)
    return bool(patterns) and any(
        matches_any(e.name, patterns) for e in catalog.entries
    )

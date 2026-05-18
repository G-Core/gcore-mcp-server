"""Code execution entry point: runs user code in a Pydantic Monty sandbox."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Sequence, cast

import pydantic_monty
from pydantic_monty import ResourceLimits

from .catalog import Catalog
from .dispatch import make_call_tool


TYPE_STUBS = """
from typing import Any
async def call_tool(tool_name: str, /, **kwargs: Any) -> Any: ...
def search_tools(query: str, limit: int = 20) -> list[dict[str, Any]]: ...
def get_tool_schema(name: str) -> dict[str, Any]: ...
project_id: int | None = None
region_id: int | None = None
"""

DEFAULT_LIMITS: dict[str, Any] = {
    "max_duration_secs": 30.0,
    "max_memory": 200_000_000,  # 200 MB
    "max_allocations": 1_000_000,
    "max_recursion_depth": 200,
}

MAX_RESULT_BYTES = 40_000
MAX_STREAM_BYTES = 40_000


@dataclass(frozen=True)
class ExecResult:
    """Typed result returned to the MCP caller."""

    ok: bool
    result: Any | None
    stdout: str
    stderr: str
    duration_ms: int
    truncated: bool
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict suitable for an MCP tool response."""
        return {
            "ok": self.ok,
            "result": self.result,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "truncated": self.truncated,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Truncation helpers
# ---------------------------------------------------------------------------


def _truncate_bytes(s: str, max_bytes: int = MAX_STREAM_BYTES) -> str:
    """Truncate ``s`` so that ``len(s.encode())`` does not exceed ``max_bytes``.

    The cut happens at a unicode-safe boundary and a short suffix is appended
    indicating how many bytes were dropped.
    """
    if not s:
        return s
    encoded = s.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return s
    cut = encoded[:max_bytes]
    text = cut.decode("utf-8", errors="ignore")
    dropped = len(encoded) - len(text.encode("utf-8"))
    return text + f"\n... [truncated, dropped {dropped} bytes]"


def _json_size(value: Any) -> int:
    """Approximate JSON byte-size of ``value``."""
    try:
        return len(json.dumps(value, default=str).encode("utf-8"))
    except Exception:
        return len(str(value).encode("utf-8"))


class _TruncationState:
    __slots__ = ("budget", "hit")

    def __init__(self, budget: int) -> None:
        self.budget: int = budget
        self.hit: bool = False


def _truncate_value(value: Any, state: _TruncationState) -> Any:
    """Depth-first walk that trims a value to fit ``state.budget``.

    Budget is decremented exactly once per scalar leaf (containers do not
    re-account their children). Containers check the remaining budget *before*
    descending into each child, so once the budget is exhausted the rest of a
    list/dict is replaced with a ``{"_truncated": True, "_dropped_items": N}``
    marker. Oversized scalar strings are truncated in place. In every
    over-budget path ``state.hit`` is set, so the surrounding ``ExecResult``
    never reports ``truncated=False`` while the byte cap was breached.
    """
    if isinstance(value, list):
        list_value: list[Any] = value  # type: ignore[assignment]
        out: list[Any] = []
        total = len(list_value)
        for idx, item in enumerate(list_value):
            if state.budget <= 0:
                state.hit = True
                out.append({"_truncated": True, "_dropped_items": total - idx})
                return out
            out.append(_truncate_value(item, state))
        return out

    if isinstance(value, dict):
        dict_value: dict[Any, Any] = value  # type: ignore[assignment]
        d: dict[Any, Any] = {}
        keys: list[Any] = list(dict_value.keys())
        total_keys = len(keys)
        for idx, key in enumerate(keys):
            if state.budget <= 0:
                state.hit = True
                d["_truncated"] = True
                d["_dropped_items"] = total_keys - idx
                return d
            d[key] = _truncate_value(dict_value[key], state)
        return d

    # Oversized strings are truncated in place so the byte cap holds even when
    # a single scalar exceeds the remaining budget.
    if isinstance(value, str):
        size = len(value.encode("utf-8"))
        if size > state.budget:
            state.hit = True
            truncated = _truncate_bytes(value, max(0, state.budget))
            state.budget -= len(truncated.encode("utf-8"))
            return truncated
        state.budget -= size
        return value

    # Other scalars (int/float/bool/None/…) are not splittable; account for
    # their size and flag truncation if they push the budget negative.
    size = _json_size(value)
    if size > state.budget:
        state.hit = True
    state.budget -= size
    return value


def _truncate_for_return(
    value: Any, max_bytes: int = MAX_RESULT_BYTES
) -> tuple[Any, bool]:
    """Return ``(trimmed, hit)`` where ``trimmed`` fits in ``max_bytes``.

    ``trimmed`` is ``value`` with oversized lists/dicts replaced past the
    budget by ``{"_truncated": True, "_dropped_items": N}`` markers and
    oversized strings cut at a unicode-safe boundary. ``hit`` is ``True`` iff
    any truncation was applied; the caller surfaces it via the ``truncated``
    flag on the surrounding ``ExecResult``.
    """
    state = _TruncationState(budget=int(max_bytes))
    trimmed = _truncate_value(value, state)
    return trimmed, state.hit


# ---------------------------------------------------------------------------
# Stream splitting
# ---------------------------------------------------------------------------


def _split_streams(stream_output: Sequence[tuple[str, str]]) -> tuple[str, str]:
    """Concat ``CollectStreams.output`` entries into separate stdout/stderr."""
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    for name, chunk in stream_output:
        if name == "stderr":
            stderr_parts.append(chunk)
        else:
            stdout_parts.append(chunk)
    return "".join(stdout_parts), "".join(stderr_parts)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def execute_code(
    code: str,
    catalog: Catalog,
    client: Any,
    timeout_secs: float = 30.0,
) -> ExecResult:
    """Run ``code`` inside a Monty sandbox and return a typed ``ExecResult``.

    The sandbox is given three external functions (``call_tool``,
    ``search_tools``, ``get_tool_schema``) and two inputs (``project_id``,
    ``region_id``). Any third-party imports inside ``code`` will fail at
    parse-time: only host-provided externals can reach the SDK.
    """
    streams = pydantic_monty.CollectStreams()
    call_tool = make_call_tool(catalog, client)

    try:
        m = await pydantic_monty.Monty.acreate(
            code,
            script_name="agent.py",
            inputs=["project_id", "region_id"],
            type_check=True,
            type_check_stubs=TYPE_STUBS,
        )
    except pydantic_monty.MontySyntaxError as e:
        return ExecResult(
            ok=False,
            result=None,
            stdout="",
            stderr="",
            duration_ms=0,
            truncated=False,
            error=e.display(format="msg"),
        )
    except pydantic_monty.MontyTypingError as e:
        return ExecResult(
            ok=False,
            result=None,
            stdout="",
            stderr="",
            duration_ms=0,
            truncated=False,
            error=e.display(format="concise"),
        )

    started = time.monotonic()
    try:
        raw_result = await m.run_async(
            inputs={
                "project_id": client.cloud_project_id,
                "region_id": client.cloud_region_id,
            },
            external_functions={
                "call_tool": call_tool,
                "search_tools": catalog.search,
                "get_tool_schema": catalog.get_schema,
            },
            limits=cast(
                ResourceLimits,
                {**DEFAULT_LIMITS, "max_duration_secs": timeout_secs},
            ),
            print_callback=streams,
        )
    except pydantic_monty.MontyRuntimeError as e:
        elapsed = int((time.monotonic() - started) * 1000)
        stdout, stderr = _split_streams(streams.output)
        return ExecResult(
            ok=False,
            result=None,
            stdout=_truncate_bytes(stdout, MAX_STREAM_BYTES),
            stderr=_truncate_bytes(stderr, MAX_STREAM_BYTES),
            duration_ms=elapsed,
            truncated=False,
            error=e.display(format="traceback"),
        )

    elapsed = int((time.monotonic() - started) * 1000)
    stdout, stderr = _split_streams(streams.output)
    trimmed_result, hit = _truncate_for_return(raw_result, MAX_RESULT_BYTES)
    return ExecResult(
        ok=True,
        result=trimmed_result,
        stdout=_truncate_bytes(stdout, MAX_STREAM_BYTES),
        stderr=_truncate_bytes(stderr, MAX_STREAM_BYTES),
        duration_ms=elapsed,
        truncated=hit,
        error=None,
    )

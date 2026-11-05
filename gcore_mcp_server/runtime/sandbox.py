"""Run model-written Python in a Pydantic Monty sandbox.

The script reaches the Gcore API only through what is injected here: typed
``gcore.*`` modules (``import gcore.dns.zones as zones``, see
``script_modules``) and the ``call_tool``, ``search_tools`` and
``get_tool_schema`` functions. Every API call goes through the same
:class:`Dispatcher` - and so the same read-only, deny-list and confirmation
checks - as a direct tool call. Monty
has no filesystem, environment, network or import access beyond a small
stdlib subset, and runs in a separate worker process with time and memory
limits.

Intermediate results stay inside the sandbox; only what the script prints or
returns reaches the model, which is what makes multi-step tasks cheap.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastmcp.exceptions import ToolError

from gcore_mcp_server.catalog import Access

from gcore_mcp_server.catalog import ToolEntry

from . import script_modules, waiting
from .dispatch import Dispatcher, call_tool_for
from .safety import ApprovalUnavailable
from .shaping import HINT_IN_SCRIPT, truncate

logger = logging.getLogger(__name__)

TYPE_STUBS = """
from typing import Any
async def call_tool(tool_name: str, /, **kwargs: Any) -> Any: ...
async def search_tools(query: str, limit: int = 10) -> list[dict[str, Any]]: ...
async def get_tool_schema(name: str) -> dict[str, Any]: ...
project_id: int | None
region_id: int | None
"""

DEFAULT_LIMITS: dict[str, Any] = {
    # CPU time inside the interpreter; time spent waiting on API calls is free.
    "max_feed_duration_secs": 20.0,
    "max_memory": 256_000_000,
    "max_recursion_depth": 200,
    # Upper bound on host round trips (API calls) per script.
    "max_suspensions": 500,
}
# Wall time per script. MCP clients commonly give up on a request after 60 s;
# stopping first means the script ends with a clear error and its output,
# instead of running on after the client stopped listening.
DEFAULT_TIMEOUT_SECS = 55.0
MAX_STREAM_CHARS = 20_000


class SandboxRunner:
    """Owns a lazily started Monty worker pool."""

    def __init__(
        self,
        dispatcher: Dispatcher,
        project_id: int | None,
        region_id: int | None,
        allow_writes: bool = False,
        timeout_secs: float = DEFAULT_TIMEOUT_SECS,
    ):
        self.dispatcher = dispatcher
        self.timeout_secs = timeout_secs
        # Read-only by default: scripts are for gathering and aggregating data;
        # changes go through call_write_tool / call_destructive_tool, which
        # clients approve one by one.
        self.allow_writes = allow_writes
        self.project_id = project_id
        self.region_id = region_id
        self._pool: Any = None
        self._lock = asyncio.Lock()

    async def _get_pool(self) -> Any:
        async with self._lock:
            if self._pool is None:
                import pydantic_monty

                # A backstop behind run()'s own timeout, which reports better.
                pool = pydantic_monty.AsyncMonty(request_timeout=self.timeout_secs + 10)
                await pool.__aenter__()
                self._pool = pool
            return self._pool

    async def aclose(self) -> None:
        if self._pool is not None:
            pool, self._pool = self._pool, None
            try:
                await pool.__aexit__(None, None, None)
            except Exception:  # pragma: no cover - best effort on shutdown
                pass

    async def run(self, code: str, ctx: Any | None = None) -> dict[str, Any]:
        """Execute ``code`` and return ``{"result", "stdout", "error", ...}``."""
        import pydantic_monty

        dispatcher = self.dispatcher
        calls = 0
        started_tasks: list[str] = []

        async def invoke(entry: ToolEntry, kwargs: dict[str, Any]) -> Any:
            """One API call from the script, by call_tool or a gcore.* module."""
            nonlocal calls
            calls += 1
            token = waiting.SCRIPT_TASKS.set(started_tasks)
            try:
                return await check_and_call(entry, kwargs)
            finally:
                waiting.SCRIPT_TASKS.reset(token)
                await _report_progress(ctx, calls)

        async def check_and_call(entry: ToolEntry, kwargs: dict[str, Any]) -> Any:
            reason = dispatcher.policy.blocked_reason(entry)
            if reason:  # read-only mode or deny-list comes first
                raise ToolError(reason)
            if not self.allow_writes and entry.access is not Access.READ:
                raise ToolError(
                    f"{entry.name} is a {entry.access.value} operation, and scripts "
                    "can only read. Make the change with "
                    f"{call_tool_for(entry.access)} instead (the server can be "
                    "started with GCORE_CODE_WRITES=true to allow it in scripts)."
                )
            # Untruncated: the script filters data before returning it. A list
            # result stays a list (no _scope wrapper), as its stub says.
            try:
                return await dispatcher.call_raw(
                    entry,
                    kwargs,
                    ctx,
                    None,
                    interactive=False,
                    wrap_non_dict=False,
                    bounded=False,
                )
            except ApprovalUnavailable as exc:
                done = (
                    f" The script stopped here; the {calls - 1} call(s) before this "
                    "one already ran. Do NOT rerun the script, or they run again."
                    if calls > 1
                    else ""
                )
                raise ToolError(
                    f"{exc}{done} Make this call with {call_tool_for(entry.access)} "
                    "and the same name and arguments; it asks the user to approve."
                ) from None

        async def call_tool(tool_name: str, /, **kwargs: Any) -> Any:
            # Scripts can't approve calls (see safety.ApprovalUnavailable).
            kwargs.pop("confirm_token", None)
            return await invoke(dispatcher.lookup(tool_name), kwargs)

        # Async like call_tool, so the rule for scripts is simply "await every
        # helper" (models awaited these when they were plain functions).
        async def search_tools(query: str, limit: int = 10) -> list[dict[str, Any]]:
            return dispatcher.catalog.search(query, limit)

        async def get_tool_schema(name: str) -> dict[str, Any]:
            return dispatcher.catalog.describe(dispatcher.lookup(name))

        not_supported = script_modules.unsupported(code)
        if not_supported:
            raise ToolError(
                "Not supported in the sandbox (nothing ran):\n"
                + "\n".join(not_supported)
            )
        paths = script_modules.imported_paths(code)
        root = script_modules.build_root(dispatcher.catalog, paths, invoke)
        pool = await self._get_pool()
        streams = pydantic_monty.CollectStreams(max_bytes=1_000_000)
        started = time.monotonic()
        out: dict[str, Any] = {}
        type_notes = ""
        try:
            async with pool.checkout(
                script_name="script.py",
                limits=DEFAULT_LIMITS,
                type_check=True,
                type_check_stubs=TYPE_STUBS,
                type_check_format="concise",
                external_modules={script_modules.ROOT: root} if root else None,
            ) as session:

                async def feed(skip_type_check: bool) -> Any:
                    return await asyncio.wait_for(
                        session.feed_run(
                            code,
                            inputs={
                                "project_id": self.project_id,
                                "region_id": self.region_id,
                            },
                            external_lookup={
                                "call_tool": call_tool,
                                "search_tools": search_tools,
                                "get_tool_schema": get_tool_schema,
                            },
                            print_callback=streams,
                            skip_type_check=skip_type_check,
                        ),
                        # One budget for the whole script: a retry without
                        # the type check gets only what is left of it.
                        timeout=max(
                            0.001,
                            self.timeout_secs - (time.monotonic() - started),
                        ),
                    )

                try:
                    result = await feed(skip_type_check=False)
                except pydantic_monty.MontyTypingError as exc:
                    report = exc.display()
                    blocked = script_modules.blocking(code, report)
                    if blocked:
                        # A definite mistake: stop before any call (or write)
                        # happens.
                        raise _Refused(
                            script_modules.explain(blocked, dispatcher.catalog, paths)
                        ) from None
                    # Only the checker's guesses ("may be None"): run, and keep
                    # its notes in case the script fails.
                    type_notes = report
                    result = await feed(skip_type_check=True)
            data, cut = truncate(result, dispatcher.max_result_chars, HINT_IN_SCRIPT)
            out["result"] = data
            if cut:
                out["truncated"] = True
        except _Refused as exc:
            out["error"] = f"Type check failed (nothing ran):\n{exc}"
        except pydantic_monty.MontySyntaxError as exc:
            out["error"] = f"Syntax error (nothing ran):\n{exc.display()}"
        except pydantic_monty.MontyRuntimeError as exc:
            out["error"] = exc.display(format="traceback")
            if type_notes:
                out["error"] += script_modules.notes_for_failure(
                    out["error"], type_notes
                )
        except asyncio.TimeoutError:
            out["error"] = (
                f"Script exceeded {self.timeout_secs:g} s and was stopped. It had "
                f"started {calls} API call(s); those that completed took effect. "
                "Split the work "
                "into smaller scripts (for example one project or region per "
                "script), or ask for fewer items."
            )
            if started_tasks:
                # Seen live: a ~90 s create_and_poll in a script; without the
                # ids the model had to find what it had started by name.
                ids = ", ".join(f"'{t}'" for t in started_tasks)
                out["error"] += (
                    f" Tasks it started go on at Gcore: {ids}. Do NOT rerun the "
                    f"script (that starts them again): wait for each with "
                    f"{waiting.TASK_POLL}(task_id=...), outside a script."
                )
        except pydantic_monty.MontyError as exc:
            out["error"] = f"Sandbox failure: {type(exc).__name__}: {exc}"
        except ToolError as exc:
            out["error"] = str(exc)

        stdout = "".join(text for stream, text in streams.output if stream == "stdout")
        stderr = "".join(text for stream, text in streams.output if stream == "stderr")
        if stdout:
            out["stdout"] = _cut(stdout)
        if stderr:
            out["stderr"] = _cut(stderr)
        out["api_calls"] = calls
        out["duration_ms"] = int((time.monotonic() - started) * 1000)
        if "error" in out:
            raise ToolError(_format_failure(out))
        return out


class _Refused(Exception):
    """The type checker found a definite mistake; the script did not run."""


async def _report_progress(ctx: Any | None, calls: int) -> None:
    """Tell the client the script is still working (one step per API call).

    Clients that extend their request timeout on progress keep waiting for a
    long script; others ignore it. Without a progress token this does nothing.
    """
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress=calls, message=f"{calls} API call(s) done")
    except Exception:  # never fail a script over a progress notice
        pass


def _cut(text: str) -> str:
    if len(text) <= MAX_STREAM_CHARS:
        return text
    return (
        text[:MAX_STREAM_CHARS] + f"\n…[{len(text) - MAX_STREAM_CHARS} more chars cut]"
    )


def _format_failure(out: dict[str, Any]) -> str:
    parts = [str(out["error"])]
    if out.get("stdout"):
        parts.append(f"--- stdout before the failure ---\n{out['stdout']}")
    parts.append(f"(api_calls={out['api_calls']}, duration_ms={out['duration_ms']})")
    return "\n".join(parts)

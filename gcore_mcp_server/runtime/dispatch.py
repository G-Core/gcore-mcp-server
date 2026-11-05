"""The single path from a tool call to the SDK."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, cast

from fastmcp.exceptions import ToolError

from gcore_mcp_server.catalog import Access, Catalog, ToolEntry
from gcore_mcp_server.catalog.typed import coerce_json_strings

from . import waiting
from .safety import LABEL_FIELDS, SafetyPolicy, describe_call
from .scope import (
    CloudScope,
    Region,
    _not_available,  # pyright: ignore[reportPrivateUsage]
    gather_regions,
    merge_region_results,
)
from gcore_mcp_server.catalog.typed import explicit_nulls

from .shaping import (
    DEFAULT_MAX_RESULT_CHARS,
    HINT_NARROW,
    HINT_WITH_CODE,
    describe_error,
    to_jsonable,
    truncate,
)

logger = logging.getLogger(__name__)

# The dynamic-mode tool that runs each access class. One tool per risk level lets
# clients approve by tool: reads run without asking, changes are confirmed.
CALL_TOOLS: dict[Access, str] = {
    Access.READ: "call_read_tool",
    Access.WRITE: "call_write_tool",
    Access.DESTRUCTIVE: "call_destructive_tool",
}


def call_tool_for(access: Access) -> str:
    return CALL_TOOLS[access]


# Items per batch call: they run in parallel, each within the wait limit.
MAX_BATCH = 20
# Looking up names for an approval prompt must never hold the call up long.
LABEL_TIMEOUT_SECS = 5.0


@dataclass
class Dispatcher:
    """Runs catalog entries with safety checks, validation and result shaping."""

    catalog: Catalog
    policy: SafetyPolicy
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS
    scope: CloudScope | None = None
    """Fills in cloud project/region the user didn't pin (see runtime/scope.py)."""
    code_execution: bool = False
    """Whether execute_code is offered, so the "result too large" hint may
    suggest it (direct mode has no execute_code)."""
    wait_secs: float | None = waiting.DEFAULT_WAIT_SECS
    """How long a ``*_and_poll`` call waits before it returns "still running"
    with its task ids (GCORE_WAIT_TIMEOUT; None waits until done)."""

    def lookup(self, name: str) -> ToolEntry:
        entry = self.catalog.resolve(name)
        if entry is None:
            if self.policy.is_denied(name):
                raise ToolError(f"{name} is blocked by the server's deny-list.")
            suggestions = self.catalog.suggest(name)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            raise ToolError(
                f"Unknown tool {name!r}.{hint} Use search_tools to find the right one."
            )
        return entry

    async def call_raw(
        self,
        entry: ToolEntry,
        arguments: dict[str, Any] | None,
        ctx: Any | None = None,
        confirm_token: str | None = None,
        interactive: bool = True,
        wrap_non_dict: bool = True,
        bounded: bool = True,
    ) -> Any:
        """Check, validate and run ``entry``; return plain JSON data (untruncated).

        ``interactive=False`` (inside execute_code) disables the
        input-required confirmation round trip, which cannot pause a script.
        ``wrap_non_dict=False`` keeps a list result a list when the default
        project was filled in (no ``{"_scope", "result"}`` wrapper), so it
        matches the operation's typed stub. ``bounded=False`` lets a polling
        call wait until its task is done (scripts have their own time limit).
        """
        args, note, fan_out = await self._prepare(entry, arguments)
        summary = None
        if self.policy.needs_confirmation(entry) and not fan_out:
            (label,) = await self._labels(entry, [args])
            summary = describe_call(entry, args, label)
        await self.policy.enforce(
            entry, args, ctx, confirm_token, interactive, summary=summary
        )
        started = time.monotonic()
        data: Any
        if fan_out:
            data = await self._call_all_regions(entry, args, fan_out)
        else:
            data = await self._run(entry, args, ctx, bounded)
        logger.info("%s ok in %.0f ms", entry.name, (time.monotonic() - started) * 1000)
        if note:
            if isinstance(data, dict):
                data = {"_scope": note, **cast(dict[str, Any], data)}
            elif wrap_non_dict:
                data = {"_scope": note, "result": data}
        return data

    async def _prepare(
        self, entry: ToolEntry, arguments: dict[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, Any] | None, list[Region] | None]:
        """Checked arguments with the cloud scope filled in, its note, and the
        regions to search when a list call names none."""
        args = coerce_json_strings(dict(arguments or {}), entry.string_params)
        unknown = sorted(set(args) - set(entry.param_names))
        if unknown:
            raise ToolError(
                f"Unknown argument(s) for {entry.name}: {', '.join(unknown)}. "
                f"Valid: {', '.join(entry.param_names) or '(none)'}."
            )
        if self.scope is None:
            return args, None, None
        # Before the safety check, so approval covers the real project.
        scoped = await self.scope.resolve(entry, args)
        return scoped.args, scoped.note, scoped.fan_out

    async def call_batch(
        self,
        entry: ToolEntry,
        items: list[Any],
        ctx: Any | None = None,
        confirm_token: str | None = None,
    ) -> Any:
        """Run ``entry`` once per item, approved together.

        Seen live: four deletes took eight calls, each refused and then
        repeated with its token. A batch is shown to the user as one list and
        approved (or confirmed with one token) once; then the items run in
        parallel, each within the wait limit, and each reports on its own.
        """
        if not items:
            raise ToolError("arguments is an empty list: give one object per item.")
        if len(items) > MAX_BATCH:
            raise ToolError(
                f"{len(items)} items: at most {MAX_BATCH} per call. Split the list."
            )
        prepared: list[dict[str, Any]] = []
        note: dict[str, Any] | None = None
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ToolError(f"Item {i}: each item must be an arguments object.")
            args, item_note, fan_out = await self._prepare(
                entry, cast(dict[str, Any], item)
            )
            if fan_out:
                raise ToolError(
                    f"Item {i}: pass region_id (a batch can't search every region)."
                )
            prepared.append(args)
            note = note or item_note
        labels = (
            await self._labels(entry, prepared)
            if self.policy.needs_confirmation(entry)
            else None
        )
        await self.policy.enforce_batch(entry, prepared, ctx, confirm_token, labels)

        async def one(i: int, args: dict[str, Any]) -> dict[str, Any]:
            try:
                return {"item": i, "result": await self._run(entry, args, ctx, True)}
            except ToolError as exc:
                return {"item": i, "error": str(exc)}

        results = await asyncio.gather(*(one(i, a) for i, a in enumerate(prepared)))
        failed = sum("error" in r for r in results)
        out: dict[str, Any] = {
            "items": len(results),
            "succeeded": len(results) - failed,
            "failed": failed,
            "results": results,
        }
        if note:
            out = {"_scope": note, **out}
        hint = HINT_WITH_CODE if self.code_execution else HINT_NARROW
        data, _ = truncate(out, self.max_result_chars, hint)
        return data

    async def _run(
        self,
        entry: ToolEntry,
        args: dict[str, Any],
        ctx: Any | None = None,
        bounded: bool = False,
    ) -> Any:
        polls = waiting.polls(entry.name)
        known = (
            [str(args["task_id"])]
            if entry.name == waiting.TASK_POLL and args.get("task_id")
            else None
        )

        async def report(elapsed: float, message: str) -> None:
            if ctx is not None:
                await ctx.report_progress(
                    progress=elapsed, total=self.wait_secs, message=message
                )

        try:
            with explicit_nulls(k for k, v in args.items() if v is None):
                result = await waiting.run(
                    entry.name,
                    lambda: entry.adapter.validate_python(args),
                    self.wait_secs if polls and bounded else None,
                    report if ctx is not None else None,
                    self._follow_up(entry),
                    known,
                )
        except ToolError:
            raise
        except Exception as exc:
            logger.info("%s failed: %s", entry.name, exc)
            raise ToolError(describe_error(exc, entry.name)) from exc
        data = to_jsonable(result)
        # Operations with no response body (most deletes) return None, which
        # clients would show as an empty result.
        return {"ok": True} if data is None else data

    async def _labels(
        self, entry: ToolEntry, items: list[dict[str, Any]]
    ) -> list[str | None]:
        """A readable name for each item's target, for the approval prompt.

        Read with the resource's own get operation (``45.82.30.198`` for a
        floating IP, the volume's name), in parallel and within a few seconds;
        an item whose target can't be read is shown by its IDs alone.
        """
        resource = entry.name.rsplit(".", 1)[0]
        get = self.catalog.resolve(f"{resource}.get")
        if get is None or get.name == entry.name:
            return [None] * len(items)

        async def label(args: dict[str, Any]) -> str | None:
            get_args = {k: v for k, v in args.items() if k in get.param_names}
            if any(p not in get_args for p in get.required_params):
                return None
            try:
                found = to_jsonable(await get.adapter.validate_python(get_args))
            except Exception:
                return None
            if not isinstance(found, dict):
                return None
            values = cast(dict[str, Any], found)
            for key in LABEL_FIELDS:
                value = values.get(key)
                if isinstance(value, (str, int)) and str(value).strip():
                    return str(value)
            return None

        try:
            return list(
                await asyncio.wait_for(
                    asyncio.gather(*(label(a) for a in items)), LABEL_TIMEOUT_SECS
                )
            )
        except asyncio.TimeoutError:
            return [None] * len(items)

    def _follow_up(self, entry: ToolEntry) -> str | None:
        """How to read the result of an operation that is still running."""
        if entry.name == waiting.TASK_POLL:
            return None
        resource = entry.name.rsplit(".", 1)[0]
        get = self.catalog.resolve(f"{resource}.get")
        if get is None:
            return None
        if "delete" in entry.name.rsplit(".", 1)[1]:
            return f"confirm it is gone with {get.name} (HTTP 404)"
        return f"read the result with {get.name}"

    async def _call_all_regions(
        self, entry: ToolEntry, args: dict[str, Any], regions: list[Region]
    ) -> Any:
        """A list call without region_id: search every active region."""

        async def one(region: Region) -> Any:
            return await self._run(entry, {**args, "region_id": region.id})

        if not regions:
            raise ToolError(f"{entry.name}: the account has no active regions.")
        per_region = await gather_regions(regions, one)
        if not any(not isinstance(d, BaseException) for _, d in per_region):
            # No region answered. "Not available here" only means there was
            # nothing to find; any other failure (403 everywhere, bad key) must
            # not turn into an empty result that reads as "you have none".
            failures = [
                d
                for _, d in per_region
                if isinstance(d, BaseException) and not _not_available(d)
            ]
            if failures:
                raise failures[0]
        merged = merge_region_results(per_region)
        merged["note"] = (
            "region_id was not given, so every active region was searched; "
            "each item shows its region_id."
        )
        return merged

    async def call(
        self,
        entry: ToolEntry,
        arguments: dict[str, Any] | None,
        ctx: Any | None = None,
        confirm_token: str | None = None,
    ) -> Any:
        """Like :meth:`call_raw`, but trimmed to the configured result size."""
        data = await self.call_raw(entry, arguments, ctx, confirm_token)
        hint = HINT_WITH_CODE if self.code_execution else HINT_NARROW
        data, _ = truncate(data, self.max_result_chars, hint)
        return data

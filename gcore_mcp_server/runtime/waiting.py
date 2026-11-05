"""Long operations: a bounded wait, task ids to follow up, progress meanwhile.

Cloud ``*_and_poll`` operations wait until their task finishes: a load
balancer takes about 90 s, a Kubernetes cluster many minutes. Many clients
give up on a tool call after 60 s (opencode, the MCP TypeScript SDK default),
while the task keeps running on Gcore's side, and a model that sees only a
timeout may start the operation again.

So a polling call waits at most ``GCORE_WAIT_TIMEOUT`` seconds. If the task is
still running then, the call returns normally, saying so, with the ids of the
tasks the operation started (recorded from its API responses) and how to
follow them up. Meanwhile a progress notification goes out every few seconds,
which lets clients that extend their timeout on progress keep waiting.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
from typing import Any, Awaitable, Callable, cast

logger = logging.getLogger(__name__)

DEFAULT_WAIT_SECS = 50.0
POLL_SUFFIX = "_and_poll"
# Waits for a task by id: bounded like the *_and_poll operations, and the way
# to wait again for a task that was still running.
TASK_POLL = "cloud.tasks.poll"


def polls(name: str) -> bool:
    return name.endswith(POLL_SUFFIX) or name == TASK_POLL


PROGRESS_EVERY_SECS = 10.0

# Task ids seen in API responses of the call being run (None: not recording).
_TASKS: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "gcore_mcp_tasks", default=None
)
# Every task id a script's calls started, so a script stopped by its time
# limit can say which tasks are still going on.
SCRIPT_TASKS: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "gcore_mcp_script_tasks", default=None
)


async def record_tasks(response: Any) -> None:
    """httpx response hook: note ``{"tasks": [...]}`` ids from changes."""
    seen, script = _TASKS.get(), SCRIPT_TASKS.get()
    if (seen is None and script is None) or response.request.method == "GET":
        return
    if "json" not in response.headers.get("content-type", ""):
        return
    try:
        await response.aread()
        body = json.loads(response.content)
    except Exception:
        return
    if not isinstance(body, dict):
        return
    tasks: Any = cast(dict[str, Any], body).get("tasks")
    if isinstance(tasks, list):
        for task in cast(list[Any], tasks):
            for sink in (seen, script):
                if sink is not None and isinstance(task, str) and task not in sink:
                    sink.append(task)


def install(client: Any) -> None:
    """Add :func:`record_tasks` to an SDK client's HTTP client (once)."""
    http = getattr(client, "_client", None)
    hooks = getattr(http, "event_hooks", None)
    if not isinstance(hooks, dict):
        return
    response = cast(dict[str, list[Any]], hooks).setdefault("response", [])
    if record_tasks not in response:
        response.append(record_tasks)


async def run(
    name: str,
    call: Callable[[], Awaitable[Any]],
    budget: float | None,
    report: Callable[[float, str], Awaitable[None]] | None = None,
    follow_up: str | None = None,
    known_tasks: list[str] | None = None,
) -> Any:
    """Run ``call``; after ``budget`` seconds return a "still running" result.

    ``budget=None`` waits as long as the call takes. ``report(elapsed,
    message)`` is called every few seconds while waiting.
    """
    seen: list[str] = list(known_tasks or [])
    script = SCRIPT_TASKS.get()
    if script is not None:  # a script waiting on a task: name it if it stops
        script.extend(t for t in seen if t not in script)
    token = _TASKS.set(seen)
    try:
        job = asyncio.ensure_future(call())
    finally:
        _TASKS.reset(token)
    started = time.monotonic()
    while True:
        elapsed = time.monotonic() - started
        step = PROGRESS_EVERY_SECS
        if budget is not None:
            step = min(step, max(0.0, budget - elapsed))
        done, _ = await asyncio.wait({job}, timeout=step)
        if done:
            return job.result()
        elapsed = time.monotonic() - started
        if budget is not None and elapsed >= budget:
            job.cancel()  # only stops waiting; the task goes on at Gcore
            logger.info("%s still running after %.0f s", name, elapsed)
            return still_running(name, elapsed, seen, follow_up)
        if report is not None:
            try:
                await report(elapsed, f"{name}: waiting for the task ({elapsed:.0f} s)")
            except Exception:  # never fail a call over a progress notice
                pass


def still_running(
    name: str, waited: float, tasks: list[str], follow_up: str | None
) -> dict[str, Any]:
    """The result of a call that outlasted the wait, with the next step."""
    if name == TASK_POLL:
        hint = (
            f"The task is still running (the server stopped waiting after "
            f"{waited:.0f} s so the call doesn't time out). To keep waiting, call "
            f"{TASK_POLL}(task_id='{tasks[0]}') again. When its state is FINISHED, "
            "created_resources has the new IDs."
            if tasks
            else "The task is still running; call it again to keep waiting."
        )
    else:
        if tasks:
            wait = (
                f"wait for it with {TASK_POLL}(task_id='{tasks[0]}') (also limited "
                f"to {waited:.0f} s per call; call it again while it says "
                "still_running). When the task is FINISHED, created_resources has "
                "the new IDs"
            )
        else:
            wait = "check the resource's status with a get or list call"
        then = f"; then {follow_up}" if follow_up else ""
        hint = (
            f"{name} was started and goes on at Gcore; the server stopped waiting "
            f"after {waited:.0f} s so the call doesn't time out. Do not call {name} "
            f"again (that would start a second one): {wait}{then}."
        )
    return {
        "still_running": True,
        "waited_s": round(waited),
        "tasks": tasks,
        "hint": hint,
    }

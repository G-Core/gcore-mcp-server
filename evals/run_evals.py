"""Model-in-the-loop evals: can Claude actually do real tasks with this server?

    uv run python -m evals.run_evals                      # Haiku, all modes
    uv run python -m evals.run_evals --model claude-sonnet-5-5 --modes dynamic

Each task is a user request run through a minimal agent loop (Anthropic
Messages API + the server's MCP tools over an in-memory client) against the
live account. The answer is checked against ground truth fetched straight
from the SDK. Reported per mode: correctness, tool calls, turns, billed input
tokens. Results are written to reports/EVALS.md and reports/evals-results.json
(git-ignored).

Needs ANTHROPIC_API_KEY plus the live-test settings in
tests/live/credentials.py. Keys are never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastmcp import Client

from gcore_mcp_server.config.server_config import Mode, ServerConfig
from gcore_mcp_server.runtime import SafetyPolicy
from gcore_mcp_server.server import create_server
from tests.live.common import (
    close_open_clients,
    live_client,
    sweep_leftovers,
    unique_name,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "EVALS.md"
RAW = ROOT / "reports" / "evals-results.json"
MAX_TURNS = 16
MAX_TOOL_RESULT_CHARS = 60_000

SYSTEM = (
    "You are an assistant operating the user's Gcore cloud account through the "
    "provided tools. Use the tools to find real data; never guess. The user has "
    "pre-approved every action in this session: if a tool says CONFIRMATION "
    "REQUIRED, treat it as approved and repeat the call with the confirm_token. "
    "Finish with a short, direct answer that states the requested numbers or names."
)


def anthropic_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY") or None


# --------------------------------------------------------------------------- tasks


@dataclass
class Task:
    id: str
    prompt: str
    truth: Callable[[Any], Awaitable[Any]]
    check: Callable[[str, Any], bool]
    writes: bool = False


def has_number(answer: str, truth: Any) -> bool:
    """The exact number appears as a count in the answer.

    Numbers inside identifiers, paths or versions (``/v1/``, ``g1-standard``,
    ``project 6``-style IDs glued to letters) don't count, and neither does an
    answer that says it couldn't find out.
    """
    if re.search(r"\b(can't|cannot|couldn't|unable to|don't have)\b", answer, re.I):
        return False
    text = re.sub(r"`[^`]*`|\S*/\S*", " ", answer.replace(",", ""))
    return bool(re.search(rf"(?<![\w.\-]){truth}(?![\w.\-])", text))


def contains_all(answer: str, truth: Any) -> bool:
    return all(str(x).lower() in answer.lower() for x in truth)


def contains_any(answer: str, truth: Any) -> bool:
    return any(str(x).lower() in answer.lower() for x in truth)


async def _all(page: Any) -> list[Any]:
    return list(getattr(page, "results", None) or [])


async def t_active_regions(c: Any) -> int:
    return sum(
        1 for r in await _all(await c.cloud.regions.list()) if r.state == "ACTIVE"
    )


async def t_projects(c: Any) -> list[str]:
    return [p.name for p in await _all(await c.cloud.projects.list())]


async def t_unattached(c: Any) -> int:
    vols = await _all(await c.cloud.volumes.list(limit=1000))
    return sum(1 for v in vols if not v.attachments and v.status == "available")


async def t_total_volume_gb(c: Any) -> int:
    return sum(v.size for v in await _all(await c.cloud.volumes.list(limit=1000)))


async def t_instance_count(c: Any) -> int:
    return (await c.cloud.instances.list(limit=1000)).count or 0


async def t_ssh_keys(c: Any) -> int:
    return (await c.cloud.ssh_keys.list(limit=1000)).count or 0


async def t_networks(c: Any) -> int:
    return (await c.cloud.networks.list(limit=1000)).count or 0


async def t_security_groups(c: Any) -> int:
    return (await c.cloud.security_groups.list(limit=1000)).count or 0


async def t_flavor_2_4(c: Any) -> list[str]:
    flavors = await _all(await c.cloud.instances.flavors.list())
    return [f.flavor_name for f in flavors if f.vcpus == 2 and f.ram == 4096]


async def t_dns_zones(c: Any) -> int:
    page = await c.dns.zones.list(limit=1000)
    return int(
        getattr(page, "total_amount", None) or len(getattr(page, "zones", []) or [])
    )


async def t_cdn_resources(c: Any) -> int:
    res = await c.cdn.cdn_resources.list()
    items = res if isinstance(res, list) else getattr(res, "results", None) or list(res)
    return len(items)


async def t_floating(c: Any) -> int:
    return (await c.cloud.floating_ips.list(limit=1000)).count or 0


async def t_region_of_project(c: Any) -> list[str]:
    regions = await _all(await c.cloud.regions.list())
    return [r.display_name for r in regions if r.id == 76]


async def t_biggest_volume(c: Any) -> list[str]:
    vols = await _all(await c.cloud.volumes.list(limit=1000))
    if not vols:
        return []  # nothing to ask about; main() skips the task
    top = max(v.size for v in vols)
    return [v.name for v in vols if v.size == top]


async def t_none(c: Any) -> None:
    return None


async def t_k8s(c: Any) -> int:
    return (await c.cloud.k8s.clusters.list()).count or 0


def ssh_lifecycle_check(answer: str, truth: Any) -> bool:
    # The real check is in run_task: the key must have been created (seen in a
    # tool result) and nothing may be left behind.
    return "delet" in answer.lower()


# Unique per run, so a concurrent run's sweep never deletes it.
EVAL_KEY = unique_name("eval-key")

TASKS: list[Task] = [
    Task(
        "active-regions",
        "How many Gcore cloud regions are currently ACTIVE?",
        t_active_regions,
        has_number,
    ),
    Task(
        "projects", "List the names of all my cloud projects.", t_projects, contains_all
    ),
    Task(
        "unattached-volumes",
        "How many volumes in my default project and region are available and not attached to any instance?",
        t_unattached,
        has_number,
    ),
    Task(
        "total-volume-size",
        "What is the total size in GB of all volumes in my default project and region?",
        t_total_volume_gb,
        has_number,
    ),
    Task(
        "instance-count",
        "How many instances (VMs) are in my default project and region?",
        t_instance_count,
        has_number,
    ),
    Task(
        "ssh-keys",
        "How many SSH keys does my default project have?",
        t_ssh_keys,
        has_number,
    ),
    Task(
        "networks",
        "How many networks exist in my default project and region?",
        t_networks,
        has_number,
    ),
    Task(
        "security-groups",
        "How many security groups are in my default project and region?",
        t_security_groups,
        has_number,
    ),
    Task(
        "flavor",
        "Which instance flavor has exactly 2 vCPUs and 4 GB RAM in my default region? Give its name.",
        t_flavor_2_4,
        contains_any,
    ),
    Task(
        "dns-zones", "How many DNS zones does my account have?", t_dns_zones, has_number
    ),
    Task(
        "cdn-resources",
        "How many CDN resources are configured on my account?",
        t_cdn_resources,
        has_number,
    ),
    Task(
        "floating-ips",
        "How many floating IPs are in my default project and region?",
        t_floating,
        has_number,
    ),
    Task(
        "region-name",
        "What is the display name of my default region (region id 76)?",
        t_region_of_project,
        contains_any,
    ),
    Task(
        "biggest-volume",
        "What is the name of the largest volume (by size) in my default project and region?",
        t_biggest_volume,
        contains_any,
    ),
    Task(
        "k8s",
        "How many managed Kubernetes clusters are in my default project and region?",
        t_k8s,
        has_number,
    ),
    Task(
        "ssh-create-delete",
        f"Create an SSH key named {EVAL_KEY} (let the platform generate it), confirm it exists, then delete it.",
        t_none,
        ssh_lifecycle_check,
        writes=True,
    ),
]


# --------------------------------------------------------------------------- agent


@dataclass
class Run:
    task: str
    mode: str
    model: str
    correct: bool = False
    answer: str = ""
    turns: int = 0
    tool_calls: int = 0
    tools_used: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    tool_def_tokens: int = 0
    seconds: float = 0.0
    created: bool = False
    error: str | None = None


def to_anthropic_tools(tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": (t.description or "")[:4000],
            "input_schema": t.input_schema,
        }
        for t in tools
    ]


# Named server variants. "direct" approximates what an unconfigured user of the
# old server got (its default toolsets); "direct-full" is a hand-tuned direct
# config that covers every task.
OLD_DEFAULT = (
    "cloud.projects,cloud.regions,cloud.tasks,cloud.quotas,"
    "cloud.placement_groups,cloud.instances"
)
VARIANTS: dict[str, tuple[Mode, str | None]] = {
    "dynamic": (Mode.DYNAMIC, None),
    "direct": (Mode.DIRECT, OLD_DEFAULT),
    "direct-full": (
        Mode.DIRECT,
        OLD_DEFAULT
        + ",cloud.networks,cloud.floating_ips,cloud.security_groups,cdn,dns.zones,"
        "cloud.k8s.clusters,cloud.volumes,cloud.ssh_keys",
    ),
}


async def run_task(task: Task, variant: str, model: str, ai: Any, truth: Any) -> Run:
    mode, tools = VARIANTS[variant]
    run = Run(task=task.id, mode=variant, model=model)
    cfg = ServerConfig(mode=mode, tools=tools, code_execution=(mode is not Mode.DIRECT))
    server = create_server(cfg, client=live_client(), policy=SafetyPolicy())
    started = time.monotonic()
    leftovers: list[str] = []
    try:
        async with Client(server) as mcp:
            tools = to_anthropic_tools(await mcp.list_tools())
            system = SYSTEM + "\n\nServer instructions:\n" + (server.instructions or "")
            count = await ai.messages.count_tokens(
                model=model,
                system=system,
                tools=tools,
                messages=[{"role": "user", "content": "x"}],
            )
            run.tool_def_tokens = count.input_tokens
            messages: list[dict[str, Any]] = [{"role": "user", "content": task.prompt}]
            for _ in range(MAX_TURNS):
                run.turns += 1
                resp = await ai.messages.create(
                    model=model,
                    max_tokens=2000,
                    system=system,
                    tools=tools,
                    messages=messages,
                )
                run.input_tokens += resp.usage.input_tokens
                run.output_tokens += resp.usage.output_tokens
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            b.model_dump(exclude_none=True) for b in resp.content
                        ],
                    }
                )
                uses = [b for b in resp.content if b.type == "tool_use"]
                if not uses:
                    run.answer = "".join(
                        b.text for b in resp.content if b.type == "text"
                    ).strip()
                    break
                results = []
                for use in uses:
                    run.tool_calls += 1
                    label = use.name
                    if use.name.startswith("call_") and use.name.endswith("_tool"):
                        label = f"{use.name}:{use.input.get('name')}"
                    run.tools_used.append(label)
                    res = await mcp.call_tool(use.name, use.input, raise_on_error=False)
                    body = "\n".join(getattr(c, "text", "") for c in res.content)[
                        :MAX_TOOL_RESULT_CHARS
                    ]
                    if not res.is_error and EVAL_KEY in body and "fingerprint" in body:
                        run.created = True
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": use.id,
                            "content": body or "(empty)",
                            "is_error": bool(res.is_error),
                        }
                    )
                messages.append({"role": "user", "content": results})
            else:
                run.error = "turn limit"
    finally:
        if task.writes:
            # Always clean up, even if the model or a tool call raised; keep the
            # original error if cleanup fails too.
            try:
                leftovers = await sweep_leftovers(live_client())
            except Exception as exc:  # pragma: no cover - best effort
                leftovers = [f"cleanup failed: {exc}"]
    run.seconds = round(time.monotonic() - started, 1)
    run.correct = bool(run.answer) and task.check(run.answer, truth)
    if task.writes:
        # Writes count only if the resource was really created (seen in a tool
        # result) and nothing is left behind.
        if leftovers:
            run.correct = False
            run.error = f"left resources: {leftovers}"
        elif not run.created:
            run.correct = False
            run.error = "the key was never created"
    await close_open_clients()
    return run


# --------------------------------------------------------------------------- report


def summarize(runs: list[Run]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keys = sorted({(r.model, r.mode) for r in runs})
    for model, mode in keys:
        rs = [r for r in runs if r.model == model and r.mode == mode]
        n = len(rs)
        out.append(
            {
                "model": model,
                "mode": mode,
                "tasks": n,
                "correct": sum(r.correct for r in rs),
                "avg_input_tokens": int(sum(r.input_tokens for r in rs) / n),
                "avg_tool_calls": round(sum(r.tool_calls for r in rs) / n, 1),
                "avg_turns": round(sum(r.turns for r in rs) / n, 1),
                "tool_def_tokens": rs[0].tool_def_tokens,
                "avg_seconds": round(sum(r.seconds for r in rs) / n, 1),
            }
        )
    return out


def write_report(runs: list[Run], truths: dict[str, Any]) -> None:
    summary = summarize(runs)
    RAW.parent.mkdir(exist_ok=True)
    RAW.write_text(
        json.dumps(
            {"summary": summary, "runs": [r.__dict__ for r in runs]},
            indent=1,
            default=str,
        )
    )
    lines = [
        "# Model evals",
        "",
        f"Generated by `uv run python -m evals.run_evals` on {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}"
        f" against a live account. {len(TASKS)} tasks, one run each per mode; answers are checked against",
        "ground truth read directly from the SDK. `input tokens` are billed input tokens summed over the",
        "whole agent loop (tool definitions are re-sent every turn). Raw data: `evals-results.json` next to this file.",
        "",
        "Modes: **dynamic** = the default four meta-tools; **direct** = the classic one-tool-per-method",
        "surface limited to project, region, task, quota, placement-group and instance operations (what",
        "the old server enabled by default); **direct-full** = direct mode hand-configured with everything the",
        "tasks need (the best case for direct mode).",
        "",
        "| model | mode | correct | avg input tokens / task | tool-definition tokens | avg tool calls | avg turns | avg seconds |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {s['model']} | {s['mode']} | {s['correct']}/{s['tasks']} | {s['avg_input_tokens']:,} | {s['tool_def_tokens']:,} | {s['avg_tool_calls']} | {s['avg_turns']} | {s['avg_seconds']} |"
            for s in summary
        ],
        "",
        "## Per task",
        "",
        "| task | model | mode | ok | calls | input tokens | tools used | note |",
        "|---|---|---|:-:|---:|---:|---|---|",
    ]
    for r in sorted(runs, key=lambda r: (r.task, r.model, r.mode)):
        used = ", ".join(dict.fromkeys(r.tools_used))[:160]
        note = (
            (
                r.error
                or (
                    ""
                    if r.correct
                    else f"answer: {r.answer[:120]!r} truth: {str(truths.get(r.task))[:80]}"
                )
            )
            .replace("|", "/")
            .replace("\n", " ")
        )
        lines.append(
            f"| {r.task} | {r.model} | {r.mode} | {'✅' if r.correct else '❌'} | {r.tool_calls} | {r.input_tokens:,} | {used} | {note} |"
        )
    lines.append("")
    REPORT.write_text("\n".join(lines))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", action="append", help="repeatable; default claude-haiku-5-5"
    )
    parser.add_argument("--modes", default="dynamic,direct")
    parser.add_argument("--tasks", default="", help="comma-separated task ids")
    parser.add_argument(
        "--append", action="store_true", help="merge with existing results"
    )
    args = parser.parse_args()

    key = anthropic_key()
    if not key:
        raise SystemExit("Set ANTHROPIC_API_KEY (and the GCORE_LIVE_* settings).")
    import anthropic

    ai = anthropic.AsyncAnthropic(api_key=key)
    models = args.model or ["claude-haiku-5-5"]
    modes = args.modes.split(",")
    unknown = [m for m in modes if m not in VARIANTS]
    if unknown:
        raise SystemExit(f"unknown modes {unknown}; choose from {list(VARIANTS)}")
    tasks = [t for t in TASKS if not args.tasks or t.id in args.tasks.split(",")]

    gc = live_client()
    truths = {t.id: await t.truth(gc) for t in tasks}
    await close_open_clients()
    # An empty list means the account has nothing to ask about (e.g. no
    # volumes); contains_all([]) would count any answer as correct.
    for t in [t for t in tasks if truths[t.id] == []]:
        print(f"skipping {t.id}: the test project has no data for it")
    tasks = [t for t in tasks if truths[t.id] != []]

    runs: list[Run] = []
    if args.append and RAW.exists():
        runs = [Run(**r) for r in json.loads(RAW.read_text())["runs"]]
        runs = [
            r
            for r in runs
            if not (
                r.model in models
                and r.mode in modes
                and r.task in {t.id for t in tasks}
            )
        ]
    for model in models:
        for mode in modes:
            for task in tasks:
                try:
                    run = await run_task(task, mode, model, ai, truths[task.id])
                except Exception as exc:  # noqa: BLE001 - record and continue
                    run = Run(
                        task=task.id,
                        mode=mode,
                        model=model,
                        error=f"{type(exc).__name__}: {str(exc)[:200]}",
                    )
                    await close_open_clients()
                runs.append(run)
                print(
                    f"{model} {mode:11} {task.id:20} {'OK ' if run.correct else 'BAD'} calls={run.tool_calls} in={run.input_tokens} {run.error or ''}",
                    flush=True,
                )
    write_report(runs, truths)
    for s in summarize(runs):
        print(s)


if __name__ == "__main__":
    asyncio.run(main())

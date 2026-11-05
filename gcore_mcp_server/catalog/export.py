"""Human-readable views of the catalog: the CLI listing and docs/OPERATIONS.md."""

from __future__ import annotations

from collections.abc import Iterable

import gcore

from .catalog import Catalog, ToolEntry, matches_any

OPERATIONS_HEADER = """\
# Operations

Every operation of the `gcore` Python SDK v{version} that this server exposes:
{count} in total. Each one is named by its SDK path, which is also what
`GCORE_TOOLS` and `GCORE_DENY_TOOLS` patterns match (see the README, "Writing
patterns").

The access class decides what needs approval and what read-only mode allows:
**read** (no side effects), **write** (creates or changes something) and
**destructive** (deletes, overwrites, interrupts or weakens something; needs
approval by default).

To check a pattern, run `gcore-mcp-server --list 'cloud.volumes.*'`.

This file is generated from the installed SDK; a test fails when it is out of
date. Regenerate it with `UPDATE_SNAPSHOTS=1 uv run pytest tests/test_catalog.py`.
"""


def _summary(entry: ToolEntry) -> str:
    return (entry.summary.splitlines() or [""])[0].replace("|", "\\|").strip()


def operations_markdown(catalog: Catalog) -> str:
    """The full catalog as Markdown, grouped by service."""
    lines = [
        OPERATIONS_HEADER.format(version=gcore.__version__, count=len(catalog.entries))
    ]
    counts = catalog.services()
    for service in sorted(counts):
        lines += [
            f"## {service} ({counts[service]})",
            "",
            "| operation | access | summary |",
            "|---|---|---|",
        ]
        lines += [
            f"| `{e.name}` | {e.access.value} | {_summary(e)} |"
            for e in catalog.entries
            if e.service == service
        ]
        lines.append("")
    return "\n".join(lines)


def list_operations(catalog: Catalog, patterns: Iterable[str] = ()) -> list[str]:
    """Lines for ``gcore-mcp-server --list``: access, name and summary."""
    # Commas too: the server's own hint suggests --list 'GCORE_TOOLS value'.
    pats = [p.strip() for arg in patterns for p in arg.split(",") if p.strip()]
    entries = [e for e in catalog.entries if not pats or matches_any(e.name, pats)]
    width = max((len(e.name) for e in entries), default=0)
    lines = [f"{e.access.value:<11} {e.name:<{width}}  {_summary(e)}" for e in entries]
    lines.append(f"{len(entries)} of {len(catalog.entries)} operations")
    return lines

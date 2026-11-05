"""Typed ``gcore.*`` modules for execute_code, and which type errors block.

A script imports API resources as modules (``import gcore.dns.zones as zones``)
and calls their operations as typed functions. This module

* finds the ``gcore.*`` imports in a script and builds just those modules for
  the sandbox, each with its generated stub (see ``catalog.stubs``), so the
  type checker knows every argument and result field;
* decides which of the checker's findings stop a script before it runs.

Only definite mistakes block: a misspelled operation, argument or result field,
a wrong value for a fixed choice, an undefined name, a module that doesn't
exist. Those would fail at runtime anyway, and stopping them first means
nothing - including no write - has happened yet. The checker's guesses
("this may be None") don't block: the script runs, and the notes are shown
only if it then fails.
"""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from gcore_mcp_server.catalog import Catalog, ToolEntry
from gcore_mcp_server.catalog.stubs import ROOT

# script.py:4:13: error[invalid-key] Unknown key ...
_DIAGNOSTIC = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+):(?P<col>\d+): "
    r"(?P<level>error|warning)\[(?P<rule>[\w-]+)\] (?P<message>.*)$",
    re.MULTILINE,
)

# Rules that are definite mistakes whatever the data turns out to be.
_ALWAYS_BLOCKING = frozenset(
    {
        "unresolved-reference",  # name not defined (e.g. json not imported)
        "unresolved-import",  # module that doesn't exist
        "possibly-missing-submodule",  # gcore.cloud used without importing .volumes
        "unknown-argument",
        "missing-argument",
        "too-many-positional-arguments",
        "parameter-already-assigned",
        "invalid-await",
    }
)


# Built-ins the sandbox runs but its type checker doesn't know (pydantic-monty
# 1.4): "Name `map` used when not defined" there is wrong, so it must not block.
CHECKER_MISSING_BUILTINS = frozenset(
    {"filter", "format", "getattr", "hasattr", "map", "open", "setattr"}
)


@dataclass(frozen=True)
class Diagnostic:
    line: int
    col: int
    rule: str
    message: str
    text: str


def diagnostics(report: str) -> list[Diagnostic]:
    return [
        Diagnostic(int(m["line"]), int(m["col"]), m["rule"], m["message"], m.group(0))
        for m in _DIAGNOSTIC.finditer(report)
    ]


def blocking(code: str, report: str) -> list[Diagnostic]:
    """The findings in ``report`` that are definite mistakes in ``code``."""
    written_keys, unpacked = _positions(code)
    return [d for d in diagnostics(report) if _is_blocking(d, written_keys, unpacked)]


def _is_blocking(
    d: Diagnostic,
    written_keys: set[tuple[int, int]],
    unpacked: set[tuple[int, int]],
) -> bool:
    if d.rule == "unresolved-reference":
        # Checked first: ``f(**undefined)`` is still an undefined name.
        name = re.search(r"Name `(\w+)`", d.message)
        return not (name and name[1] in CHECKER_MISSING_BUILTINS)
    if (d.line, d.col) in unpacked:
        # ``f(**args)``: the checker can't know which keys the dict holds, so
        # it reports every parameter the dict's value type could miss.
        return False
    if d.rule in _ALWAYS_BLOCKING:
        return True
    if d.rule == "invalid-key":
        # Reading a key a result doesn't have is a typo; writing a new key
        # (``item["project_name"] = ...``) is the script annotating its data.
        return (d.line, d.col) not in written_keys
    if d.rule == "unresolved-attribute":
        # ``Module gcore.x has no member y``: an operation that doesn't exist.
        # Not "attribute upper on None": that's only a maybe.
        return d.message.startswith("Module ")
    if d.rule == "invalid-argument-type":
        # Wrong value for an argument (``group_by='projects'``, a number for
        # an ID): one definite type. Not a union (``str | int`` from the
        # script's own dicts, ``str | None`` from ``.get``) and not an unknown
        # type: those are guesses about values that are usually right.
        found = re.search(r"found `(.*)`$", d.message)
        return (
            bool(found)
            and not _is_union(found[1])
            and not re.search(r"\b(None|Unknown|Any)\b", found[1])
        )
    return False


MAX_NOTES = 3
MAX_NOTE_CHARS = 300


def notes_for_failure(traceback: str, report: str) -> str:
    """The checker's notes most likely to explain a failure, for its error.

    Notes on the failing line first, otherwise the nearest ones before it
    (``x: int = 'a'`` explains a failure one line later); at most three, each
    shortened. The rest are only counted: they are guesses about code that
    didn't fail, and can run to pages (long inferred union types).
    """
    lines = re.findall(r"line (\d+)", traceback)
    failed = int(lines[-1]) if lines else None
    notes = diagnostics(report)
    if failed is None:
        chosen = notes[:MAX_NOTES]
    else:
        chosen = [d for d in notes if d.line == failed][:MAX_NOTES]
        if not chosen:
            before = sorted(
                (d for d in notes if d.line < failed), key=lambda d: -d.line
            )
            chosen = before[:MAX_NOTES]
    out = ""
    if chosen:
        shown = [
            d.text if len(d.text) <= MAX_NOTE_CHARS else d.text[:MAX_NOTE_CHARS] + "…"
            for d in chosen
        ]
        out += "\n--- type checker notes (may explain the failure) ---\n"
        out += "\n".join(shown)
    others = len(notes) - len(chosen)
    if others:
        out += f"\n({others} more type checker note(s) left out.)"
    return out


def _is_union(type_text: str) -> bool:
    """``a | b`` at the top level (not inside ``list[a | b]``)."""
    depth = 0
    for i, ch in enumerate(type_text):
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        elif ch == "|" and depth == 0 and type_text[i - 1 : i + 2] == " | ":
            return True
    return False


# Arguments the sandbox's runtime rejects although its type stubs accept them,
# so the checker can't catch them and a script would fail partway (possibly
# after its first changes).
_UNSUPPORTED_KEYWORDS: dict[tuple[str, str], frozenset[str] | None] = {
    ("json", "dumps"): frozenset({"default", "cls"}),
    ("json", "dump"): frozenset({"default", "cls"}),
    ("asyncio", "gather"): None,  # no keyword arguments at all
}


def unsupported(code: str) -> list[str]:
    """Calls the sandbox can't run, found before anything runs."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            continue
        key = (node.func.value.id, node.func.attr)
        if key not in _UNSUPPORTED_KEYWORDS:
            continue
        banned = _UNSUPPORTED_KEYWORDS[key]
        for kw in node.keywords:
            if kw.arg is not None and (banned is None or kw.arg in banned):
                call = ".".join(key)
                fix = (
                    "convert values with str() first"
                    if call.startswith("json")
                    else "handle errors inside each awaited call instead"
                )
                found.append(
                    f"script.py:{node.lineno}:{kw.col_offset + 1}: {call}() doesn't "
                    f"support {kw.arg}= in this sandbox; {fix}."
                )
    return found


def _positions(code: str) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Positions (line, 1-based column) of written keys and ``**`` arguments.

    ``x[key] = ...`` reports at ``key``; ``f(**args)`` at the ``**``.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set(), set()
    written: set[tuple[int, int]] = set()
    unpacked: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            written.add((node.slice.lineno, node.slice.col_offset + 1))
        elif isinstance(node, ast.keyword) and node.arg is None:
            unpacked.add((node.lineno, node.col_offset + 1))
            unpacked.add((node.value.lineno, node.value.col_offset + 1))
    return written, unpacked


def explain(
    blocked: list[Diagnostic], catalog: Catalog, paths: set[str] | None = None
) -> str:
    """The blocking findings, with hints: close module names, and the keys a
    result really has when a script reads one it doesn't (list items sit
    under ``results`` in most services, ``zones``/``apps``/``items`` in others).
    """
    lines = [d.text for d in blocked]
    sources = [
        catalog.stub(p).source for p in sorted(paths or ()) if p in catalog.module_paths
    ]
    for d in blocked:
        typed = re.search(r"for TypedDict `(\w+)`", d.message)
        if d.rule == "invalid-key" and typed:
            keys = _typed_dict_keys(typed[1], sources)
            if keys:
                lines.append(f"  `{typed[1]}` has the keys: " + ", ".join(keys) + ".")
        missing = re.search(r"module `gcore\.([\w.]+)`", d.message)
        if d.rule == "unresolved-import" and missing:
            close = difflib.get_close_matches(
                missing[1], sorted(catalog.package_paths), n=3, cutoff=0.6
            )
            if close:
                lines.append(
                    "  Did you mean: " + ", ".join(f"gcore.{c}" for c in close) + "?"
                )
        if d.rule == "possibly-missing-submodule":
            lines.append(
                "  Import each resource you call: "
                "`import gcore.cloud.volumes as volumes`."
            )
    return "\n".join(lines)


_CLASS = re.compile(r"^class (\w+)\(([^)]*)\):\n((?:    .*\n?)*)", re.MULTILINE)
_FIELD = re.compile(r"^    (\w+):", re.MULTILINE)


def _typed_dict_keys(name: str, sources: list[str], depth: int = 0) -> list[str]:
    """The keys of TypedDict ``name`` in the generated stubs, bases included."""
    for source in sources:
        for m in _CLASS.finditer(source):
            if m[1] != name:
                continue
            keys: list[str] = []
            for base in m[2].split(","):
                base = base.strip()
                if base and base != "TypedDict" and "=" not in base and depth < 5:
                    keys += _typed_dict_keys(base, sources, depth + 1)
            keys += _FIELD.findall(m[3])
            return list(dict.fromkeys(keys))
    return []


# ---------------------------------------------------------------- modules


def imported_paths(code: str) -> set[str]:
    """Resource paths a script imports from ``gcore`` (``cloud.volumes``)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(f"{ROOT}."):
                    paths.add(alias.name[len(ROOT) + 1 :])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == ROOT or node.module.startswith(f"{ROOT}."):
                base = node.module[len(ROOT) + 1 :]
                for alias in node.names:  # from gcore.cloud import volumes
                    paths.add(f"{base}.{alias.name}".strip("."))
    return paths


def build_root(
    catalog: Catalog,
    paths: set[str],
    call: Callable[[ToolEntry, dict[str, Any]], Awaitable[Any]],
) -> Any | None:
    """The ``gcore`` package with the imported resources, or ``None``.

    Paths that aren't resources (typos, or an operation imported by name) are
    left out; the type checker then reports them as unresolved.
    """
    import pydantic_monty

    wanted = {p for p in paths if p in catalog.package_paths}
    if not wanted:
        return None
    # Every ancestor too: gcore.cloud.load_balancers.listeners needs
    # gcore.cloud and gcore.cloud.load_balancers.
    for path in list(wanted):
        parts = path.split(".")
        wanted.update(".".join(parts[:i]) for i in range(1, len(parts)))

    def node(path: str) -> Any:
        prefix = f"{path}." if path else ""
        children = {
            p[len(prefix) :]: node(p)
            for p in wanted
            if p.startswith(prefix) and "." not in p[len(prefix) :]
        }
        functions: dict[str, Any] = {}
        stub = ""
        if path in catalog.module_paths:
            stub = catalog.stub(path).source
            for entry in catalog.module_entries(path):
                functions[entry.name.rsplit(".", 1)[-1]] = _function(entry, call)
        return pydantic_monty.ExternalModule({**functions, **children}, stubs=stub)

    return node("")


def _function(
    entry: ToolEntry, call: Callable[[ToolEntry, dict[str, Any]], Awaitable[Any]]
) -> Callable[..., Awaitable[Any]]:
    async def operation(**kwargs: Any) -> Any:
        return await call(entry, kwargs)

    operation.__name__ = entry.name.rsplit(".", 1)[-1]
    return operation

"""Parse the Google-style docstrings the Gcore SDK generates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SECTION = re.compile(r"^(Args|Returns|Raises|Example|Examples|Note):\s*$")
_ARG_LINE = re.compile(r"^(\s+)([A-Za-z_][A-Za-z0-9_]*):\s?(.*)$")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class ParsedDoc:
    """A docstring split into a summary, the full description and per-arg text."""

    summary: str
    description: str
    args: dict[str, str] = field(default_factory=dict[str, str])


def _squash(text: str) -> str:
    return _WS.sub(" ", text).strip()


def parse_docstring(doc: str | None) -> ParsedDoc:
    """Split an SDK docstring into summary, description and argument docs.

    ``summary`` is the first sentence (one line, for search results),
    ``description`` everything before the ``Args:`` section, and ``args`` maps
    each parameter name to its whitespace-normalized description.
    """
    if not doc:
        return ParsedDoc(summary="", description="")

    lines = doc.expandtabs().splitlines()
    body: list[str] = []
    args: dict[str, list[str]] = {}
    section: str | None = None
    current: str | None = None
    arg_indent = 0

    for line in lines:
        header = _SECTION.match(line.strip()) if not line.startswith(" ") else None
        if header:
            section = header.group(1)
            current = None
            continue
        if section is None:
            body.append(line)
            continue
        if section != "Args":
            continue
        m = _ARG_LINE.match(line)
        if m and (current is None or len(m.group(1)) <= arg_indent):
            arg_indent = len(m.group(1))
            name = m.group(2)
            current = name
            args[name] = [m.group(3)]
        elif current is not None:
            args[current].append(line)

    description = "\n".join(body).strip()
    flat = _squash(description)
    match = re.search(r"(?<=[.!?])\s", flat)
    summary = flat[: match.start()] if match else flat
    return ParsedDoc(
        summary=summary,
        description=description,
        args={k: _squash(" ".join(v)) for k, v in args.items() if _squash(" ".join(v))},
    )

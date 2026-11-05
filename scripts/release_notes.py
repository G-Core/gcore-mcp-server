"""Print a version's CHANGELOG.md section as GitHub release notes.

    python scripts/release_notes.py 1.1.0 > release-notes.md

CHANGELOG.md is wrapped at about 80 columns, but GitHub shows every line break
in a release body as a break, so wrapped lines are joined back into one line
per paragraph or list item. Headings, list items, blank lines, code blocks and
tables keep their own lines. Exits 1 if the section is missing or empty.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A line that starts a new block rather than continuing the one above it.
_BLOCK_START = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\||```|~~~)")


def section(changelog: str, version: str) -> str:
    """The body of ``## [version]``, up to the next ``## [`` heading."""
    lines: list[str] = []
    inside = False
    for line in changelog.splitlines():
        if line.startswith("## ["):
            if inside:
                break
            inside = line.startswith(f"## [{version}]")
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines).strip("\n")


def unwrap(text: str) -> str:
    """Join hard-wrapped lines; keep block structure and code blocks as is."""
    out: list[str] = []
    in_code = False
    for line in text.splitlines():
        fence = line.lstrip().startswith(("```", "~~~"))
        if in_code or fence:
            out.append(line)
            if fence:
                in_code = not in_code
            continue
        joinable = (
            out
            and out[-1].strip()
            and line.strip()
            and not _BLOCK_START.match(line)
            and not out[-1].lstrip().startswith(("#", "|"))
        )
        if joinable:
            out[-1] = f"{out[-1].rstrip()} {line.strip()}"
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: release_notes.py VERSION", file=sys.stderr)
        return 2
    body = section((ROOT / "CHANGELOG.md").read_text(), argv[0])
    if not body.strip():
        print(f"::error::CHANGELOG.md has no section for {argv[0]}", file=sys.stderr)
        return 1
    sys.stdout.write(unwrap(body))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""scripts/release_notes.py: a CHANGELOG.md section as GitHub release notes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]


def _notes() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "release_notes", ROOT / "scripts" / "release_notes.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHANGELOG = """# Changelog

Intro text.

## [1.2.0] - 2026-12-01

Built and tested against gcore SDK 0.62.0.

### Added

- **A feature** that is described
  over two lines.
- Another item.

A paragraph that is
wrapped too.

```bash
uvx gcore-mcp-server
  --flag
```

## [1.1.0] - 2026-11-05

Older notes.
"""


def test_section_is_unwrapped_and_keeps_its_blocks() -> None:
    notes = _notes()
    body = notes.unwrap(notes.section(CHANGELOG, "1.2.0"))
    assert body == (
        "Built and tested against gcore SDK 0.62.0.\n"
        "\n"
        "### Added\n"
        "\n"
        "- **A feature** that is described over two lines.\n"
        "- Another item.\n"
        "\n"
        "A paragraph that is wrapped too.\n"
        "\n"
        "```bash\n"
        "uvx gcore-mcp-server\n"
        "  --flag\n"
        "```\n"
    )


def test_missing_section_is_empty() -> None:
    assert _notes().section(CHANGELOG, "9.9.9") == ""


@pytest.mark.parametrize("line", ["### Fixed", "- item", "1. step", "| a | b |"])
def test_block_starts_are_not_joined(line: str) -> None:
    assert _notes().unwrap(f"text\n{line}\n") == f"text\n{line}\n"


def test_every_released_section_has_no_wrapped_lines() -> None:
    """Each line of the notes is a whole paragraph, list item or heading."""
    notes = _notes()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    versions = [
        line[4:].split("]")[0]
        for line in changelog.splitlines()
        if line.startswith("## [")
    ]
    assert versions
    for version in versions:
        body = notes.unwrap(notes.section(changelog, version))
        assert body.strip(), version
        for line in body.splitlines():
            assert not line.startswith("  "), (version, line)

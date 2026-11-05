"""Every place that states a version agrees, so CI fails on a missed bump.

The server's version lives in pyproject.toml; the SDK's in its exact pin
there. A release bumps both by hand, and each copy below is checked against
them.
"""

from __future__ import annotations

import re
from pathlib import Path

import gcore
import pytest

from gcore_mcp_server import __version__

ROOT = Path(__file__).parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text()


def _one(pattern: str, text: str, where: str) -> str:
    found = re.search(pattern, text, re.M)
    assert found, f"{where}: no match for {pattern!r}"
    return found.group(1)


# tomllib needs Python 3.11; the project supports 3.10.
PYPROJECT = _read("pyproject.toml")
VERSION = _one(r'^version = "([^"]+)"', PYPROJECT, "pyproject.toml")
SDK_PIN = _one(r'"gcore==([^"]+)"', PYPROJECT, "pyproject.toml gcore pin")


def _locked(package: str) -> str:
    lock = _read("uv.lock")
    return _one(
        rf'^\[\[package\]\]\nname = "{re.escape(package)}"\nversion = "([^"]+)"',
        lock,
        f"uv.lock {package}",
    )


def _released_section() -> tuple[str, str]:
    """Version and body of the newest released section of CHANGELOG.md."""
    changelog = _read("CHANGELOG.md")
    sections = re.split(r"^## ", changelog, flags=re.M)[1:]
    released = [s for s in sections if not s.startswith("[Unreleased]")]
    assert released, "CHANGELOG.md has no released section"
    version = _one(r"^\[([^\]]+)\]", released[0], "CHANGELOG.md heading")
    return version, released[0]


def test_installed_package_matches_pyproject() -> None:
    assert __version__ == VERSION, "reinstall: uv sync"


def test_lockfile_matches_pyproject() -> None:
    assert _locked("gcore-mcp-server") == VERSION, "run: uv lock"
    assert _locked("gcore") == SDK_PIN, "run: uv lock"


def test_installed_sdk_matches_the_pin() -> None:
    assert gcore.__version__ == SDK_PIN, "run: uv sync"


def test_changelog_has_the_current_version() -> None:
    version, body = _released_section()
    assert version == VERSION, (
        f"CHANGELOG.md's newest release is {version}, pyproject.toml says {VERSION}"
    )
    tested = _one(r"against gcore SDK ([0-9][^\s.]*(?:\.[0-9]+)*)", body, "CHANGELOG")
    assert tested == SDK_PIN


def test_readme_pins_the_current_release() -> None:
    pins = set(
        re.findall(r"gcore-mcp-server\.git@v([0-9][^\s`\"')]*)", _read("README.md"))
    )
    assert pins == {VERSION}, f"README.md pins {sorted(pins)}, not v{VERSION}"


def test_operations_list_names_the_pinned_sdk() -> None:
    stated = _one(
        r"`gcore` Python SDK v([^\s]+) ", _read("docs/OPERATIONS.md"), "OPERATIONS.md"
    )
    assert stated == SDK_PIN, "run: UPDATE_SNAPSHOTS=1 uv run pytest"


@pytest.mark.anyio
async def test_server_states_both_versions(anyio_backend: str) -> None:
    from fastmcp import Client

    from tests.helpers import make_server

    mcp = make_server()
    instructions = mcp.instructions or ""
    assert instructions.startswith(f"gcore-mcp-server {VERSION}:")
    assert f"SDK v{SDK_PIN}" in instructions
    async with Client(mcp) as client:
        info = client.server_info or (await client.initialize()).serverInfo
        assert info is not None and info.version == VERSION


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

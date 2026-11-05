"""Every place that states a version agrees, so CI fails on a missed bump.

The server's version lives in pyproject.toml; the SDK's in its exact pin
there. A release bumps both by hand, and each copy below is checked against
them.
"""

from __future__ import annotations

import re
import tomllib
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


PROJECT = tomllib.loads(_read("pyproject.toml"))["project"]
VERSION: str = PROJECT["version"]
SDK_PIN = next(
    d.split("==")[1] for d in PROJECT["dependencies"] if d.startswith("gcore==")
)


def _locked(package: str) -> str:
    lock = _read("uv.lock")
    return _one(
        rf'^\[\[package\]\]\nname = "{re.escape(package)}"\nversion = "([^"]+)"',
        lock,
        f"uv.lock {package}",
    )


def _released_section() -> tuple[str, str]:
    """Version and body of the newest (first) section of CHANGELOG.md.

    There is no Unreleased section: each change to the server is a release.
    """
    changelog = _read("CHANGELOG.md")
    sections = re.split(r"^## ", changelog, flags=re.M)[1:]
    assert sections, "CHANGELOG.md has no release section"
    version = _one(r"^\[([^\]]+)\]", sections[0], "CHANGELOG.md heading")
    return version, sections[0]


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


def _check_version():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_version", ROOT / "scripts" / "check_version.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("version", "latest", "server_changed", "release", "error"),
    [
        ("1.0.1", "1.0.0", True, True, None),  # a bumped fix releases
        ("1.0.0", "1.0.0", False, False, None),  # docs only: no release
        ("1.0.0", "1.0.0", True, False, "raise the version"),  # forgot the bump
        ("0.9.0", "1.0.0", False, False, "below the latest"),
        ("1.1.0", None, True, True, None),  # first release
        ("1.0.2", "1.0.0", True, False, "no '## [1.0.2]'"),  # no notes
    ],
)
def test_version_check_rules(
    version: str,
    latest: str | None,
    server_changed: bool,
    release: bool,
    error: str | None,
) -> None:
    from packaging.version import Version

    check = _check_version()
    changelog = "## [1.1.0] - x\n\n## [1.0.1] - x\n\n## [1.0.0] - x\n"
    got_release, got_error = check.decide(
        Version(version), Version(latest) if latest else None, server_changed, changelog
    )
    assert got_release is release
    if error is None:
        assert got_error is None
    else:
        assert got_error and error in got_error


@pytest.mark.parametrize(
    ("version", "latest", "base", "server_changed", "release", "error"),
    [
        # Another PR bumped main to 1.1.0 and isn't tagged yet; this one too.
        ("1.1.0", "1.0.0", "1.1.0", True, False, "already on the base branch"),
        ("1.2.0", "1.0.0", "1.1.0", True, True, None),  # raised above main
        ("1.0.1", "1.0.0", "1.1.0", True, False, "below 1.1.0 on the base"),
        # Docs-only PR after main was bumped but not tagged: it carries 1.1.0.
        ("1.1.0", "1.0.0", "1.1.0", False, True, None),
        ("1.1.0", "1.1.0", "1.1.0", False, False, None),  # docs-only, released
    ],
)
def test_version_check_against_the_base_branch(
    version: str,
    latest: str,
    base: str,
    server_changed: bool,
    release: bool,
    error: str | None,
) -> None:
    from packaging.version import Version

    check = _check_version()
    changelog = "## [1.2.0] - x\n\n## [1.1.0] - x\n\n## [1.0.1] - x\n\n## [1.0.0] - x\n"
    got_release, got_error = check.decide(
        Version(version), Version(latest), server_changed, changelog, Version(base)
    )
    assert got_release is release
    if error is None:
        assert got_error is None
    else:
        assert got_error and error in got_error


def test_version_check_paths_and_tags() -> None:
    check = _check_version()
    assert check.changes_server(["gcore_mcp_server/server.py"])
    assert check.changes_server(["README.md", "pyproject.toml"])
    assert not check.changes_server(["README.md", "tests/test_x.py", "uv.lock"])
    assert (
        str(check.latest_release(["v1.0.0", "v1.10.0", "v1.9.3", "x", "vbad"]))
        == "1.10.0"
    )
    assert check.latest_release([]) is None

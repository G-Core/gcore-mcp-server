"""Check the version in pyproject.toml against the latest release tag.

    python scripts/check_version.py --base origin/main   # a pull request
    python scripts/check_version.py                     # main after a merge

Rules:

- The version never goes below the latest ``vX.Y.Z`` tag.
- A pull request that changes the server (``gcore_mcp_server/`` or
  ``pyproject.toml``) must raise it above the latest tag: merging it releases
  that version. Docs- and tests-only changes may keep it.
- A version above the latest tag needs its ``## [X.Y.Z]`` section in
  CHANGELOG.md, which becomes the release notes.

Prints ``release=true|false`` and ``version=X.Y.Z`` (for GITHUB_OUTPUT) and
exits 1 with the reason when a rule is broken. Needs the tags fetched.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATHS = ("gcore_mcp_server/", "pyproject.toml")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def project_version() -> Version:
    text = (ROOT / "pyproject.toml").read_text()
    found = re.search(r'^version = "([^"]+)"', text, re.M)
    if not found:
        raise SystemExit("pyproject.toml has no version")
    return Version(found.group(1))


def latest_release(tags: list[str]) -> Version | None:
    versions: list[Version] = []
    for tag in tags:
        if not tag.startswith("v"):
            continue
        try:
            versions.append(Version(tag[1:]))
        except InvalidVersion:
            continue
    return max(versions, default=None)


def changes_server(paths: list[str]) -> bool:
    return any(p == s or p.startswith(s) for p in paths for s in SERVER_PATHS)


def has_changelog_section(version: Version, changelog: str) -> bool:
    return re.search(rf"^## \[{re.escape(str(version))}\]", changelog, re.M) is not None


def decide(
    version: Version,
    latest: Version | None,
    server_changed: bool,
    changelog: str,
) -> tuple[bool, str | None]:
    """``(release, error)``: whether this version is new, and what's wrong."""
    if latest is not None and version < latest:
        return False, f"version {version} is below the latest release v{latest}"
    release = latest is None or version > latest
    if server_changed and not release:
        return False, (
            f"this changes the server, so raise the version above v{latest} in "
            "pyproject.toml (patch for fixes, minor for features, major for "
            "breaking changes) and add its CHANGELOG.md section"
        )
    if release and not has_changelog_section(version, changelog):
        return (
            False,
            f"CHANGELOG.md has no '## [{version}]' section for the release notes",
        )
    return release, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the version against the latest release."
    )
    parser.add_argument("--base", help="the pull request's base ref, e.g. origin/main")
    args = parser.parse_args(argv)

    version = project_version()
    latest = latest_release(_git("tag", "--list", "v*").split())
    changed: list[str] = []
    if args.base:
        changed = _git("diff", "--name-only", f"{args.base}...HEAD").split()
    release, error = decide(
        version, latest, changes_server(changed), (ROOT / "CHANGELOG.md").read_text()
    )
    print(f"version={version}")
    print(f"release={'true' if release else 'false'}")
    if error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

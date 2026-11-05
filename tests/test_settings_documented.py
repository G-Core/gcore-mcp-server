"""Every setting the server reads is documented in .env.sample and the README."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Read by the gcore SDK client the server creates; users set them the same way.
SDK_SETTINGS = {
    "GCORE_API_KEY",
    "GCORE_BASE_URL",
    "GCORE_CLOUD_PROJECT_ID",
    "GCORE_CLOUD_REGION_ID",
    "GCORE_POLLING_TIMEOUT_SECONDS",
}
# Read by the SDK too, but removed by the server (see make_client).
IGNORED = {"GCORE_CUSTOM_HEADERS"}
LIVE_SETTINGS = {"ANTHROPIC_API_KEY"}
# Older spellings, still accepted: named next to the setting they alias.
ALIASES = {"GCORE_MCP_ROUTING", "GCORE_ELICITATION"}


def server_settings() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "gcore_mcp_server").rglob("*.py"):
        names |= set(re.findall(r"\bGCORE_[A-Z0-9_]*[A-Z0-9]\b", path.read_text()))
    return (names | SDK_SETTINGS) - IGNORED


def live_settings() -> set[str]:
    names: set[str] = set(LIVE_SETTINGS)
    for path in (ROOT / "tests" / "live").rglob("*.py"):
        names |= set(re.findall(r"\bGCORE_LIVE_[A-Z0-9_]*[A-Z0-9]\b", path.read_text()))
    return names


def test_the_sdk_still_reads_the_settings_we_document() -> None:
    import gcore._client

    source = Path(gcore._client.__file__).read_text()
    read = set(re.findall(r'os\.environ\.get\("(GCORE_[A-Z_]+)"\)', source))
    assert read == SDK_SETTINGS | IGNORED, (
        "update SDK_SETTINGS (or IGNORED), .env.sample and the README"
    )


def test_custom_headers_from_the_environment_are_ignored(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from gcore_mcp_server.server import make_client

    monkeypatch.setenv("GCORE_API_KEY", "k")
    monkeypatch.setenv("GCORE_CUSTOM_HEADERS", "Authorization: Bearer other\nX-A: 1")
    client = make_client()
    headers = client.default_headers
    assert headers["Authorization"] != "Bearer other" and "X-A" not in headers
    assert "GCORE_CUSTOM_HEADERS is ignored" in caplog.text


@pytest.mark.parametrize("name", sorted(server_settings()))
def test_server_setting_is_documented(name: str) -> None:
    sample = (ROOT / ".env.sample").read_text()
    reference = (ROOT / "README.md").read_text().split("## Configuration reference")[1]
    if name in ALIASES:
        assert name in sample, f"{name}: .env.sample"
    else:
        assert re.search(rf"^#? ?{name}=", sample, re.M), f"{name}: .env.sample"
    assert name in reference, f"{name}: README configuration reference"


@pytest.mark.parametrize("name", sorted(live_settings()))
def test_live_setting_is_documented(name: str) -> None:
    assert name in (ROOT / ".env.sample").read_text(), f"{name}: .env.sample"
    assert name in (ROOT / "CONTRIBUTING.md").read_text(), f"{name}: CONTRIBUTING.md"

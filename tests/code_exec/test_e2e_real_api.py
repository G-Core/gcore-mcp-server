"""End-to-end test against the real Gcore API.

Gated on a usable ``GCORE_API_KEY``. The test loads credentials from the
nearby ``../gcore-terraform/.env`` file if a key is not already in the
environment — this matches the local-dev convention used by the project
owner. CI runs without that file should simply skip these tests.

Run explicitly with::

    uv run pytest tests/code_exec/test_e2e_real_api.py -v -s
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest


_KNOWN_KEYS = ("GCORE_API_KEY", "GCORE_CLOUD_PROJECT_ID", "GCORE_CLOUD_REGION_ID")


def _read_real_creds() -> dict[str, str]:
    """Read real Gcore credentials, preferring ``../gcore-terraform/.env``.

    The repo owner keeps real credentials in a sibling repo's ``.env``; the
    shell environment is unreliable because the session-scoped autouse
    fixture in ``tests/conftest.py`` may have already injected a placeholder.
    We therefore prefer the file, and only fall back to the shell environment
    when the file does not exist.
    """
    captured: dict[str, str] = {}

    candidate = Path(__file__).resolve().parents[2].parent / "gcore-terraform" / ".env"
    if candidate.is_file():
        for raw in candidate.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in _KNOWN_KEYS and value:
                captured[key] = value

    if "GCORE_API_KEY" not in captured:
        for key in _KNOWN_KEYS:
            value = os.environ.get(key, "")
            if value and not value.startswith(("test-", "dummy")):
                captured.setdefault(key, value)

    return captured


_REAL_CREDS = _read_real_creds()
_HAS_REAL_KEY = bool(_REAL_CREDS.get("GCORE_API_KEY"))

pytestmark = pytest.mark.skipif(
    not _HAS_REAL_KEY,
    reason="No real GCORE_API_KEY available — set the env var or create "
    "../gcore-terraform/.env to run e2e tests.",
)


@pytest.fixture
def real_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A real Gcore client constructed with the captured real credentials.

    Re-applies the captured credentials to ``os.environ`` for the duration of
    this test, undoing the dummy key set by the session-scoped autouse
    fixture in the top-level conftest. Also clears the module-level SDK
    inspection cache so methods get rebound to this real client (other test
    files run earlier may have populated the cache with methods bound to a
    dummy-keyed client).
    """
    for key, value in _REAL_CREDS.items():
        monkeypatch.setenv(key, value)

    from gcore import Gcore
    from gcore_mcp_server.core.inspection import clear_inspection_cache

    clear_inspection_cache()

    try:
        client = Gcore()
    except Exception as exc:  # pragma: no cover - defensive
        pytest.skip(f"Gcore client init failed: {exc}")
    return client


@pytest.fixture
def real_catalog(real_client: Any) -> Any:
    from gcore_mcp_server.code_exec import build_catalog

    return build_catalog(real_client)


def test_catalog_built_from_real_client(real_catalog: Any) -> None:
    """Catalog construction succeeds against the real Gcore client."""
    assert len(real_catalog.entries) > 100
    # A few well-known tools must always be present.
    for name in ("cloud.regions.list", "cloud.projects.list", "cloud.instances.list"):
        assert name in real_catalog.by_name, f"missing canonical tool: {name}"


def test_search_finds_regions_list(real_catalog: Any) -> None:
    """Searching the real catalog returns expected ranking for a known query."""
    hits = real_catalog.search("list regions", limit=5)
    names = [h["name"] for h in hits]
    assert "cloud.regions.list" in names, f"cloud.regions.list not in top 5: {names}"


def test_get_schema_for_regions_list(real_catalog: Any) -> None:
    """get_schema on a real tool returns a JSON-shaped dict."""
    schema = real_catalog.get_schema("cloud.regions.list")
    assert schema["name"] == "cloud.regions.list"
    assert isinstance(schema["params"], list)
    # cloud.regions.list does not require project_id or region_id.
    assert schema["requires_project"] is False
    assert schema["requires_region"] is False


@pytest.mark.anyio
async def test_execute_code_calls_real_gcore_api(
    real_client: Any, real_catalog: Any
) -> None:
    """A sandbox script hits the real API via call_tool and returns a region id."""
    from gcore_mcp_server.code_exec import execute_code

    code = (
        "regions = await call_tool('cloud.regions.list')\n"
        "items = regions['results'] if isinstance(regions, dict) "
        "and 'results' in regions else regions\n"
        "items[0]['id']"
    )

    result = await execute_code(code, real_catalog, real_client, timeout_secs=20.0)

    assert result.ok, f"execute_code failed: {result.error!r}"
    assert isinstance(result.result, int), (
        f"expected an integer region id, got {result.result!r}"
    )
    assert result.duration_ms >= 0
    assert result.truncated is False


@pytest.mark.anyio
async def test_execute_code_search_and_call_pattern(
    real_client: Any, real_catalog: Any
) -> None:
    """Discover-then-call: sandbox script searches, then calls a real tool.

    Verifies the *pattern* of chaining search_tools and call_tool inside one
    sandbox invocation. Exact BM25 ranking is covered by separate unit and
    e2e tests; here we only assert that both calls succeed and return
    well-shaped data.
    """
    from gcore_mcp_server.code_exec import execute_code

    code = (
        "hits = search_tools('list regions', limit=5)\n"
        "names = [h['name'] for h in hits]\n"
        "regions = await call_tool('cloud.regions.list')\n"
        "items = regions['results'] if isinstance(regions, dict) "
        "and 'results' in regions else regions\n"
        "{'hit_names': names, 'region_count': len(items)}"
    )

    result = await execute_code(code, real_catalog, real_client, timeout_secs=20.0)

    assert result.ok, f"execute_code failed: {result.error!r}"
    payload = result.result
    assert isinstance(payload, dict)
    assert isinstance(payload["hit_names"], list) and payload["hit_names"]
    assert "cloud.regions.list" in payload["hit_names"], (
        f"cloud.regions.list not in top-5 search hits: {payload['hit_names']}"
    )
    assert isinstance(payload["region_count"], int) and payload["region_count"] >= 1


@pytest.mark.anyio
async def test_execute_code_unknown_tool_surfaces_error(
    real_client: Any, real_catalog: Any
) -> None:
    """Calling an unknown tool inside the sandbox produces a clean error."""
    from gcore_mcp_server.code_exec import execute_code

    code = "await call_tool('nope.does.not.exist')"
    result = await execute_code(code, real_catalog, real_client, timeout_secs=10.0)

    assert result.ok is False
    assert result.error is not None
    assert "nope.does.not.exist" in result.error

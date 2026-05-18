"""Tests for ``execute_code`` — Monty sandbox + result shape contract."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from gcore_mcp_server.code_exec.catalog import Catalog, ToolEntry
from gcore_mcp_server.code_exec.runner import execute_code


def _entry(method: Any, *, full_name: str = "foo.bar") -> ToolEntry:
    """Build a minimal ToolEntry for sandbox-driven tests."""
    return ToolEntry(
        full_name=full_name,
        short_name="",
        doc_short="",
        doc_full="",
        params=[],
        toolset=None,
        requires_project=False,
        requires_region=False,
        method=method,
    )


def _make_client(*, project_id: Any = None, region_id: Any = None) -> Mock:
    client = Mock()
    client.cloud_project_id = project_id
    client.cloud_region_id = region_id
    return client


@pytest.mark.anyio
async def test_execute_code_trivial():
    """A trivial expression returns its value via ExecResult.result."""
    catalog = Catalog([])
    client = _make_client()

    res = await execute_code("1 + 2", catalog, client)

    assert res.ok is True
    assert res.result == 3
    assert res.error is None


@pytest.mark.anyio
async def test_execute_code_with_stdout():
    """``print()`` calls are captured in ExecResult.stdout."""
    catalog = Catalog([])
    client = _make_client()

    res = await execute_code('print("hi")\n42', catalog, client)

    assert res.ok is True
    assert res.result == 42
    assert "hi" in res.stdout


@pytest.mark.anyio
async def test_execute_code_with_search_tools():
    """``search_tools`` is callable inside the sandbox."""
    method = Mock(return_value="ignored")
    catalog = Catalog([_entry(method, full_name="foo.bar")])
    client = _make_client()

    code = "search_tools('foo')"
    res = await execute_code(code, catalog, client)

    assert res.ok is True, f"sandbox failed: {res.error}"
    assert isinstance(res.result, list)
    # The single catalog entry should rank in the result.
    names = [r.get("name") for r in res.result]
    assert "foo.bar" in names


@pytest.mark.anyio
async def test_execute_code_with_call_tool():
    """``await call_tool(...)`` dispatches through the catalog and returns the result."""
    method = Mock(return_value={"value": 7})
    catalog = Catalog([_entry(method, full_name="foo.bar")])
    client = _make_client()

    code = "result = await call_tool('foo.bar')\nresult['value']"
    res = await execute_code(code, catalog, client)

    assert res.ok is True, f"sandbox failed: {res.error}"
    assert res.result == 7
    method.assert_called_once()


@pytest.mark.anyio
async def test_execute_code_syntax_error():
    """Garbage code returns ok=False with a non-empty error message."""
    catalog = Catalog([])
    client = _make_client()

    res = await execute_code("this is not valid !@#$", catalog, client)

    assert res.ok is False
    assert res.result is None
    assert isinstance(res.error, str) and res.error.strip() != ""


@pytest.mark.anyio
async def test_execute_code_runtime_error():
    """An uncaught Python exception surfaces in ExecResult.error."""
    catalog = Catalog([])
    client = _make_client()

    res = await execute_code('raise ValueError("boom")', catalog, client)

    assert res.ok is False
    assert res.result is None
    assert res.error is not None
    assert "boom" in res.error


@pytest.mark.anyio
async def test_execute_code_timeout():
    """An infinite loop trips the sandbox's max-duration limit."""
    catalog = Catalog([])
    client = _make_client()

    res = await execute_code(
        "x = 0\nwhile True:\n    x = x + 1",
        catalog,
        client,
        timeout_secs=0.1,
    )

    assert res.ok is False
    assert res.error is not None
    # The Monty resource-limit message mentions "duration" or "time".
    error_lower = res.error.lower()
    assert "duration" in error_lower or "time" in error_lower or "limit" in error_lower


@pytest.mark.anyio
async def test_execute_code_oversize_result_truncated():
    """A code-produced oversized payload is truncated and ``truncated=True``."""
    catalog = Catalog([])
    client = _make_client()

    code = "[{'i': i, 'pad': 'x' * 200} for i in range(10_000)]"
    res = await execute_code(code, catalog, client)

    assert res.ok is True, f"sandbox failed: {res.error}"
    assert res.truncated is True


@pytest.mark.anyio
async def test_execute_code_async_await():
    """``await`` of an async sandbox method is supported end-to-end."""
    method = AsyncMock(return_value={"async_ok": True})
    catalog = Catalog([_entry(method, full_name="foo.bar")])
    client = _make_client()

    code = "r = await call_tool('foo.bar')\nr['async_ok']"
    res = await execute_code(code, catalog, client)

    assert res.ok is True, f"sandbox failed: {res.error}"
    assert res.result is True


@pytest.mark.anyio
async def test_execute_code_to_dict_contract():
    """ExecResult.to_dict() contains the documented keys and JSON-serializes."""
    catalog = Catalog([])
    client = _make_client()

    res = await execute_code("42", catalog, client)
    d = res.to_dict()

    expected_keys = {
        "ok",
        "result",
        "stdout",
        "stderr",
        "duration_ms",
        "truncated",
        "error",
    }
    assert expected_keys <= set(d.keys())

    # Round-trip via JSON to confirm serializability.
    encoded = json.dumps(d)
    decoded = json.loads(encoded)
    assert decoded["ok"] is True
    assert decoded["result"] == 42

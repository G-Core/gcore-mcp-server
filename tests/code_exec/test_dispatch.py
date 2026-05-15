"""Tests for the host-side ``call_tool`` dispatcher used inside the sandbox."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel

from gcore_mcp_server.code_exec.catalog import Catalog, ToolEntry
from gcore_mcp_server.code_exec.dispatch import make_call_tool
from gcore_mcp_server.domain import (
    PROJECT_ID_REQUIRED_ERROR,
    REGION_ID_REQUIRED_ERROR,
)


def _entry(
    method: Any,
    *,
    full_name: str = "foo.bar",
    short_name: str = "",
    requires_project: bool = False,
    requires_region: bool = False,
) -> ToolEntry:
    """Build a minimal ToolEntry with sensible defaults."""
    return ToolEntry(
        full_name=full_name,
        short_name=short_name,
        doc_short="",
        doc_full="",
        params=[],
        toolset=None,
        requires_project=requires_project,
        requires_region=requires_region,
        method=method,
    )


def _make_client(*, project_id: Any = None, region_id: Any = None) -> Mock:
    """Build a Mock client with cloud_project_id / cloud_region_id attributes."""
    client = Mock()
    client.cloud_project_id = project_id
    client.cloud_region_id = region_id
    return client


@pytest.mark.anyio
async def test_call_tool_dispatches_sync_method():
    """A sync SDK method is invoked and its result returned (serialized)."""
    method = Mock(return_value={"ok": True})
    catalog = Catalog([_entry(method, full_name="foo.bar")])
    call_tool = make_call_tool(catalog, _make_client())

    result = await call_tool("foo.bar", limit=10)

    assert result == {"ok": True}
    method.assert_called_once_with(limit=10)


@pytest.mark.anyio
async def test_call_tool_awaits_async_method():
    """An awaitable result is awaited before being returned."""
    method = AsyncMock(return_value={"value": 42})
    catalog = Catalog([_entry(method, full_name="foo.bar")])
    call_tool = make_call_tool(catalog, _make_client())

    result = await call_tool("foo.bar")

    assert result == {"value": 42}
    method.assert_awaited_once()


@pytest.mark.anyio
async def test_call_tool_auto_injects_project_id():
    """``project_id`` is auto-injected when the method requires it and caller omits it."""
    method = Mock(return_value="ok")
    catalog = Catalog([_entry(method, full_name="foo.bar", requires_project=True)])
    call_tool = make_call_tool(catalog, _make_client(project_id=42))

    await call_tool("foo.bar")

    method.assert_called_once_with(project_id=42)


@pytest.mark.anyio
async def test_call_tool_auto_injects_region_id():
    """``region_id`` is auto-injected when the method requires it and caller omits it."""
    method = Mock(return_value="ok")
    catalog = Catalog([_entry(method, full_name="foo.bar", requires_region=True)])
    call_tool = make_call_tool(catalog, _make_client(region_id=7))

    await call_tool("foo.bar")

    method.assert_called_once_with(region_id=7)


@pytest.mark.anyio
async def test_call_tool_explicit_project_overrides_default():
    """An explicit ``project_id=`` is preserved even if the client has a default."""
    method = Mock(return_value="ok")
    catalog = Catalog([_entry(method, full_name="foo.bar", requires_project=True)])
    call_tool = make_call_tool(catalog, _make_client(project_id=1))

    await call_tool("foo.bar", project_id=999)

    method.assert_called_once_with(project_id=999)


@pytest.mark.anyio
async def test_call_tool_raises_on_unknown_name():
    """Unknown tool name raises KeyError mentioning the name and ``search_tools``."""
    catalog = Catalog([])
    call_tool = make_call_tool(catalog, _make_client())

    with pytest.raises(KeyError) as exc:
        await call_tool("does.not.exist")

    msg = str(exc.value)
    assert "does.not.exist" in msg
    assert "search_tools" in msg


@pytest.mark.anyio
async def test_call_tool_raises_when_project_required_but_unset():
    """When ``project_id`` is required and unavailable, ValueError surfaces the error."""
    method = Mock(return_value="ok")
    catalog = Catalog([_entry(method, full_name="foo.bar", requires_project=True)])
    call_tool = make_call_tool(catalog, _make_client(project_id=None))

    with pytest.raises(ValueError) as exc:
        await call_tool("foo.bar")

    assert str(exc.value) == PROJECT_ID_REQUIRED_ERROR
    method.assert_not_called()


@pytest.mark.anyio
async def test_call_tool_raises_when_region_required_but_unset():
    """When ``region_id`` is required and unavailable, ValueError surfaces the error."""
    method = Mock(return_value="ok")
    catalog = Catalog([_entry(method, full_name="foo.bar", requires_region=True)])
    call_tool = make_call_tool(catalog, _make_client(region_id=None))

    with pytest.raises(ValueError) as exc:
        await call_tool("foo.bar")

    assert str(exc.value) == REGION_ID_REQUIRED_ERROR
    method.assert_not_called()


@pytest.mark.anyio
async def test_call_tool_serializes_pydantic_models():
    """Pydantic v2 model returns are reduced to plain dicts before crossing the boundary."""

    class MyModel(BaseModel):
        name: str
        count: int

    method = Mock(return_value=MyModel(name="hi", count=3))
    catalog = Catalog([_entry(method, full_name="foo.bar")])
    call_tool = make_call_tool(catalog, _make_client())

    result = await call_tool("foo.bar")

    assert isinstance(result, dict)
    assert result == {"name": "hi", "count": 3}


@pytest.mark.anyio
async def test_call_tool_short_name_lookup():
    """``call_tool`` accepts a short-name entry registered in ``catalog.by_name``."""
    method = Mock(return_value="ok")
    catalog = Catalog([_entry(method, full_name="foo.bar.baz", short_name="fbb")])
    call_tool = make_call_tool(catalog, _make_client())

    result = await call_tool("fbb")

    assert result == "ok"
    method.assert_called_once_with()

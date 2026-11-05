"""MCP protocol tests: the server as a client sees it, with the API mocked."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client

from gcore_mcp_server.config.server_config import Mode, ServerConfig

from tests.helpers import (
    BASE_URL,
    PROJECT_ID,
    REGION_ID,
    data,
    make_server,
    text,
    tool_tokens,
)

pytestmark = pytest.mark.anyio

DYNAMIC_TOOLS = {
    "search_tools",
    "get_tool_schema",
    "call_read_tool",
    "call_write_tool",
    "call_destructive_tool",
    "execute_code",
}

# Token budgets for tools/list (o200k encoding). They are deliberately tight:
# raising one should be a conscious decision recorded in the README.
BUDGET_DYNAMIC = 1_300
BUDGET_DIRECT_INSTANCES = 25_000


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        yield mock


INSTANCES = {
    "count": 3,
    "results": [
        {"id": f"i-{n}", "name": f"vm-{n}", "status": "ACTIVE", "region_id": REGION_ID}
        for n in range(3)
    ],
}


# ---------------------------------------------------------------- tool surface


async def test_dynamic_mode_lists_meta_tools_within_budget() -> None:
    async with Client(make_server()) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools} == DYNAMIC_TOOLS
    assert tool_tokens(tools) <= BUDGET_DYNAMIC


async def test_code_execution_can_be_disabled() -> None:
    async with Client(make_server(code_execution=False)) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools} == DYNAMIC_TOOLS - {"execute_code"}


async def test_direct_mode_patterns_within_budget() -> None:
    async with Client(make_server(Mode.DIRECT, tools="cloud.instances")) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert "cloud_instances_list" in names
    assert "cloud_projects_list" in names and "cloud_regions_list" in names
    assert not names & DYNAMIC_TOOLS
    assert tool_tokens(tools) <= BUDGET_DIRECT_INSTANCES


@pytest.mark.parametrize(
    ("mode", "tools"),
    [
        (Mode.DIRECT, "management,instances"),  # toolset names from older versions
        (Mode.DYNAMIC, "cloud.instance.*"),  # typo
    ],
)
def test_tool_selection_matching_nothing_refuses_to_start(
    mode: Mode, tools: str
) -> None:
    """GCORE_TOOLS restricts the server; a bad value must not widen it."""
    from gcore_mcp_server.server import ConfigError

    with pytest.raises(ConfigError, match="matches no operation"):
        make_server(mode, tools=tools)


async def test_direct_mode_without_patterns_uses_dynamic_mode() -> None:
    async with Client(make_server(Mode.DIRECT, tools=None)) as client:
        tools_listed = await client.list_tools()
        hits = data(
            await client.call_tool("search_tools", {"query": "dns zones", "limit": 1})
        )
    assert {t.name for t in tools_listed} == DYNAMIC_TOOLS
    assert hits[0]["name"] == "dns.zones.list"


async def test_direct_mode_patterns() -> None:
    async with Client(make_server(Mode.DIRECT, tools="cloud.ssh_keys.*")) as client:
        names = {t.name for t in await client.list_tools()}
    assert {
        "cloud_ssh_keys_list",
        "cloud_ssh_keys_create",
        "cloud_ssh_keys_delete",
    } <= names


async def test_annotations_reflect_access() -> None:
    async with Client(make_server(Mode.DIRECT, tools="cloud.ssh_keys.*")) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert tools["cloud_ssh_keys_list"].annotations.read_only_hint is True
    assert tools["cloud_ssh_keys_create"].annotations.read_only_hint is False
    assert tools["cloud_ssh_keys_create"].annotations.destructive_hint is False
    assert tools["cloud_ssh_keys_delete"].annotations.destructive_hint is True
    # Destructive tools accept a confirmation token; reads do not.
    assert "confirm_token" in tools["cloud_ssh_keys_delete"].input_schema["properties"]
    assert (
        "confirm_token" not in tools["cloud_ssh_keys_list"].input_schema["properties"]
    )


async def test_dynamic_annotations() -> None:
    async with Client(make_server()) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert tools["search_tools"].annotations.read_only_hint is True
    assert tools["get_tool_schema"].annotations.read_only_hint is True
    # One call tool per risk level, so clients can approve by tool.
    assert tools["call_read_tool"].annotations.read_only_hint is True
    assert tools["call_write_tool"].annotations.read_only_hint is False
    assert tools["call_write_tool"].annotations.destructive_hint is False
    assert tools["call_destructive_tool"].annotations.destructive_hint is True
    # Scripts are read-only by default.
    assert tools["execute_code"].annotations.read_only_hint is True


def test_backward_compatible_mode_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GCORE_MCP_MODE", "GCORE_MCP_ROUTING", "GCORE_TOOLS"):
        monkeypatch.delenv(var, raising=False)
    assert ServerConfig.from_env().mode is Mode.DYNAMIC
    monkeypatch.setenv("GCORE_TOOLS", "cloud.instances.*")
    assert ServerConfig.from_env().mode is Mode.DIRECT
    monkeypatch.setenv("GCORE_MCP_MODE", "hybrid")  # removed mode
    cfg = ServerConfig.from_env()
    assert cfg.mode is Mode.DYNAMIC and "removed" in cfg.notes[0]
    monkeypatch.delenv("GCORE_MCP_MODE")
    monkeypatch.setenv("GCORE_MCP_ROUTING", "code_exec")  # older spelling
    assert ServerConfig.from_env().mode is Mode.DYNAMIC
    monkeypatch.setenv("GCORE_MCP_ROUTING", "bogus")
    cfg = ServerConfig.from_env()
    assert cfg.mode is Mode.DYNAMIC and cfg.notes


async def test_instructions_mention_defaults_and_workflow() -> None:
    mcp = make_server()
    assert f"pinned to {PROJECT_ID}" in mcp.instructions
    assert "search_tools" in mcp.instructions
    assert "_and_poll" in mcp.instructions


# ---------------------------------------------------------------- discovery


async def test_search_and_schema_round_trip() -> None:
    async with Client(make_server()) as client:
        hits = data(
            await client.call_tool(
                "search_tools", {"query": "list instances", "limit": 3}
            )
        )
        assert hits[0]["name"] == "cloud.instances.list"
        schema = data(
            await client.call_tool("get_tool_schema", {"name": hits[0]["name"]})
        )
    assert schema["access"] == "read"
    assert "project_id" in schema["input_schema"]["properties"]
    assert schema["returns"]["list_key"] == "results"


async def test_search_with_no_match_suggests_services() -> None:
    async with Client(make_server()) as client:
        out = data(await client.call_tool("search_tools", {"query": "zzzqqq"}))
    assert "cloud" in out[0]["note"]


async def test_unknown_tool_suggests_alternatives() -> None:
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_read_tool", {"name": "cloud.instance.list"}, raise_on_error=False
        )
    assert res.is_error
    assert "cloud.instances.list" in text(res)


# ---------------------------------------------------------------- calling


async def test_call_tool_injects_default_project_and_region(
    api: respx.MockRouter,
) -> None:
    route = api.get(f"/cloud/v1/instances/{PROJECT_ID}/{REGION_ID}").mock(
        return_value=httpx.Response(200, json=INSTANCES)
    )
    async with Client(make_server()) as client:
        res = await client.call_tool("call_read_tool", {"name": "cloud.instances.list"})
    assert route.called
    assert data(res)["results"][0]["name"] == "vm-0"


async def test_explicit_project_overrides_default(api: respx.MockRouter) -> None:
    route = api.get("/cloud/v1/instances/999/5").mock(
        return_value=httpx.Response(200, json=INSTANCES)
    )
    async with Client(make_server()) as client:
        await client.call_tool(
            "call_read_tool",
            {
                "name": "cloud.instances.list",
                "arguments": {"project_id": 999, "region_id": 5},
            },
        )
    assert route.called


async def test_direct_tool_call(api: respx.MockRouter) -> None:
    route = api.get(f"/cloud/v1/instances/{PROJECT_ID}/{REGION_ID}").mock(
        return_value=httpx.Response(200, json=INSTANCES)
    )
    async with Client(make_server(Mode.DIRECT, tools="cloud.instances.*")) as client:
        res = await client.call_tool("cloud_instances_list", {"limit": 2})
    assert route.called
    assert route.calls.last.request.url.params["limit"] == "2"
    assert data(res)["count"] == 3


async def test_none_fields_are_dropped(api: respx.MockRouter) -> None:
    api.get(f"/cloud/v1/instances/{PROJECT_ID}/{REGION_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "count": 1,
                "results": [{"id": "x", "name": "a", "task_state": None}],
            },
        )
    )
    async with Client(make_server()) as client:
        res = await client.call_tool("call_read_tool", {"name": "cloud.instances.list"})
    assert "task_state" not in text(res)


async def test_json_string_arguments_are_decoded(api: respx.MockRouter) -> None:
    """Some clients send a nested list/object parameter as a JSON string."""
    route = api.post(re.compile(r"/dns/v2/zones/.*")).mock(
        return_value=httpx.Response(200, json={"name": "www.example.com"})
    )
    records = [{"content": ["192.0.2.10"]}]
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_write_tool",
            {
                "name": "dns.zones.rrsets.create",
                "arguments": {
                    "zone_name": "example.com",
                    "rrset_name": "www.example.com",
                    "rrset_type": "A",
                    "resource_records": json.dumps(records),  # encoded
                },
            },
            raise_on_error=False,
        )
    assert not res.is_error, text(res)
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent["resource_records"] == records


async def test_unknown_argument_is_rejected_with_valid_names() -> None:
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_write_tool",
            {"name": "cloud.ssh_keys.create", "arguments": {"nmae": "a"}},
            raise_on_error=False,
        )
    assert res.is_error
    assert "nmae" in text(res) and "name" in text(res)


async def test_missing_required_argument_points_to_schema() -> None:
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_write_tool",
            {"name": "cloud.ssh_keys.create", "arguments": {}},
            raise_on_error=False,
        )
    assert res.is_error
    assert "get_tool_schema" in text(res)


@pytest.mark.parametrize(
    ("status", "hint"),
    [
        (404, "Not found"),
        (403, "not allowed"),
        (401, "GCORE_API_KEY"),
        (422, "get_tool_schema"),
    ],
)
async def test_api_errors_are_explained(
    api: respx.MockRouter, status: int, hint: str
) -> None:
    api.get(re.compile(r"/cloud/v1/instances/.*")).mock(
        return_value=httpx.Response(status, json={"message": "nope"})
    )
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_read_tool",
            {"name": "cloud.instances.get", "arguments": {"instance_id": "x"}},
            raise_on_error=False,
        )
    assert res.is_error
    assert f"HTTP {status}" in text(res) and hint in text(res)


async def test_large_results_are_truncated_with_a_hint(api: respx.MockRouter) -> None:
    big = {
        "count": 500,
        "results": [{"id": f"i-{n}", "name": "x" * 200} for n in range(500)],
    }
    api.get(f"/cloud/v1/instances/{PROJECT_ID}/{REGION_ID}").mock(
        return_value=httpx.Response(200, json=big)
    )
    async with Client(make_server(max_result_chars=5_000)) as client:
        res = await client.call_tool("call_read_tool", {"name": "cloud.instances.list"})
    out = data(res)
    assert len(text(res)) < 6_000
    assert out["_truncated"]["total"] == 500
    assert 0 < out["_truncated"]["shown"] < 500
    assert "execute_code" in out["_truncated"]["hint"]


async def test_delete_without_body_returns_ok(api: respx.MockRouter) -> None:
    api.delete(f"/cloud/v1/ssh_keys/{PROJECT_ID}/k1").mock(
        return_value=httpx.Response(204)
    )
    from gcore_mcp_server.runtime import ConfirmMode, SafetyPolicy

    async with Client(
        make_server(policy=SafetyPolicy(confirm=ConfirmMode.NONE))
    ) as client:
        res = await client.call_tool(
            "call_destructive_tool",
            {"name": "cloud.ssh_keys.delete", "arguments": {"ssh_key_id": "k1"}},
        )
    assert data(res) == {"ok": True}


# ---------------------------------------------------------------- code execution


async def test_execute_code_runs_calls_in_parallel_and_filters(
    api: respx.MockRouter,
) -> None:
    api.get(f"/cloud/v1/instances/{PROJECT_ID}/{REGION_ID}").mock(
        return_value=httpx.Response(200, json=INSTANCES)
    )
    api.get(re.compile(r"/cloud/v1/instances/\d+/\d+/i-\d+$")).mock(
        side_effect=lambda req: httpx.Response(
            200,
            json={
                "id": req.url.path.rsplit("/", 1)[-1],
                "name": "vm",
                "status": "ACTIVE",
            },
        )
    )
    code = """
import asyncio
page = await call_tool('cloud.instances.list')
ids = [i['id'] for i in page['results']]
details = await asyncio.gather(*[call_tool('cloud.instances.get', instance_id=i) for i in ids])
print('fetched', len(details))
sorted(d['id'] for d in details)
"""
    async with Client(make_server()) as client:
        out = data(await client.call_tool("execute_code", {"code": code}))
    assert out["result"] == ["i-0", "i-1", "i-2"]
    assert out["api_calls"] == 4
    assert out["stdout"] == "fetched 3\n"


async def test_execute_code_reports_errors_with_traceback(
    api: respx.MockRouter,
) -> None:
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "execute_code",
            {"code": "x = 1\nprint('before')\n1/0"},
            raise_on_error=False,
        )
    assert res.is_error
    assert "ZeroDivisionError" in text(res) and "before" in text(res)


async def test_read_only_scripts_run_despite_type_checker_objections(
    api: respx.MockRouter,
) -> None:
    """The checker rejects code that runs fine; read-only scripts run anyway."""
    code = "d = {'a': 1}\nv = d.get('a')\nv + 1"  # v may be None, says the checker
    async with Client(make_server()) as client:
        out = data(await client.call_tool("execute_code", {"code": code}))
    assert out["result"] == 2


async def test_type_notes_are_shown_when_a_read_only_script_fails(
    api: respx.MockRouter,
) -> None:
    code = "x: int = 'a'\nx + 1"
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error and "TypeError" in text(res)
    assert "type checker notes" in text(res)


async def test_a_definite_mistake_stops_a_write_script_before_its_first_change(
    api: respx.MockRouter,
) -> None:
    """A script that would fail halfway must not start its writes."""
    code = (
        "import gcore.cloud.ssh_keys as keys\n"
        "await keys.create(name='n')\n"
        "await keys.delete(ssh_key_id='k1', projectid=1)"  # misspelled argument
    )
    async with Client(make_server(code_writes=True)) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error and "Type check failed (nothing ran)" in text(res)
    assert [c.request.method for c in api.calls] == []


async def test_script_helpers_are_awaited(api: respx.MockRouter) -> None:
    code = (
        "hits = await search_tools('dns zones', 3)\n"
        "schema = await get_tool_schema(hits[0]['name'])\n"
        "schema['name'] == hits[0]['name']"
    )
    async with Client(make_server()) as client:
        out = data(await client.call_tool("execute_code", {"code": code}))
    assert out["result"] is True


async def test_slow_scripts_stop_before_the_client_gives_up(
    api: respx.MockRouter,
) -> None:
    import asyncio

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(3)
        return httpx.Response(200, json={"count": 0, "results": []})

    api.get(re.compile(r"/cloud/v1/ssh_keys/.*")).mock(side_effect=slow)
    code = "print('started')\nawait call_tool('cloud.ssh_keys.list')"
    async with Client(make_server(code_timeout_secs=0.5)) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    message = text(res)
    assert res.is_error and "exceeded 0s" not in message
    assert "was stopped" in message and "Split the work" in message
    assert "started" in message  # output so far is kept


async def test_scripts_report_progress(api: respx.MockRouter) -> None:
    api.get(re.compile(r"/cloud/v1/ssh_keys/.*")).mock(
        return_value=httpx.Response(200, json={"count": 0, "results": []})
    )
    seen: list[float] = []

    async def on_progress(progress: float, total: Any, message: Any) -> None:
        seen.append(progress)

    code = (
        "await call_tool('cloud.ssh_keys.list')\nawait call_tool('cloud.ssh_keys.list')"
    )
    async with Client(make_server()) as client:
        await client.call_tool(
            "execute_code", {"code": code}, progress_handler=on_progress
        )
    assert seen == [1, 2]


def test_code_timeout_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    from gcore_mcp_server.config.server_config import ServerConfig

    monkeypatch.setenv("GCORE_CODE_TIMEOUT", "120")
    assert ServerConfig.from_env().code_timeout_secs == 120
    monkeypatch.setenv("GCORE_CODE_TIMEOUT", "soon")
    config = ServerConfig.from_env()
    assert config.code_timeout_secs == 55 and "GCORE_CODE_TIMEOUT" in config.notes[-1]


@pytest.mark.parametrize(
    "code",
    [
        "open('/etc/passwd').read()",
        "import os\nos.environ.get('GCORE_API_KEY')",
        "import socket",
        "import subprocess",
    ],
)
async def test_sandbox_has_no_host_access(code: str) -> None:
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error
    assert "test-key" not in text(res)


async def test_sandbox_api_errors_are_catchable(api: respx.MockRouter) -> None:
    api.get(re.compile(r"/cloud/v1/instances/.*")).mock(
        return_value=httpx.Response(404, json={"message": "gone"})
    )
    code = """
try:
    await call_tool('cloud.instances.get', instance_id='nope')
    r = 'no error'
except Exception as e:
    r = 'caught: ' + str(e)[:40]
r
"""
    async with Client(make_server()) as client:
        out = data(await client.call_tool("execute_code", {"code": code}))
    assert out["result"].startswith("caught")


def _tools(result: Any) -> list[str]:
    return [t["name"] for t in result]


async def test_console_script_over_stdio() -> None:
    """The real entry point, launched as a subprocess the way clients do."""
    import os
    import shutil

    from fastmcp.client.transports import StdioTransport

    exe = shutil.which("gcore-mcp-server")
    if exe is None:
        pytest.skip("console script not installed in this environment")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GCORE_")}
    env["GCORE_API_KEY"] = "test-key"
    transport = StdioTransport(command=exe, args=[], env=env)
    async with Client(transport) as client:
        tools = await client.list_tools()
        hits = data(
            await client.call_tool(
                "search_tools", {"query": "list instances", "limit": 1}
            )
        )
    assert {t.name for t in tools} == DYNAMIC_TOOLS
    assert hits[0]["name"] == "cloud.instances.list"


def test_cli_list_needs_no_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from gcore_mcp_server import server

    monkeypatch.delenv("GCORE_API_KEY", raising=False)
    server.main(["--list", "dns.zones.rrsets.*"])
    out = capsys.readouterr().out
    assert "dns.zones.rrsets.delete" in out and "destructive" in out
    assert "cloud." not in out


async def test_server_reports_its_own_version() -> None:
    import re
    from pathlib import Path

    from gcore_mcp_server import __version__

    # tomllib needs Python 3.11; the project supports 3.10.
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text()
    declared = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    assert declared and __version__ == declared.group(1)
    async with Client(make_server()) as client:
        info = client.server_info or (await client.initialize()).serverInfo
        assert info is not None and info.version == __version__


async def test_requests_carry_the_server_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gcore

    from gcore_mcp_server import __version__, server

    monkeypatch.setenv("GCORE_API_KEY", "test-key")
    monkeypatch.setenv("GCORE_BASE_URL", BASE_URL)
    client = server.make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/cloud/v1/regions").mock(
            return_value=httpx.Response(200, json={"count": 0, "results": []})
        )
        await client.cloud.regions.list()
    await client.close()
    assert route.calls.last.request.headers["user-agent"] == (
        f"gcore-mcp-server/{__version__} AsyncGcore/Python {gcore.__version__}"
    )

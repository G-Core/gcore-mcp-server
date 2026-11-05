"""Tests against the real Gcore API, through the MCP protocol.

Skipped unless a live key is available (see credentials.py). Every resource is
named ``mcp-test-*``, deleted in ``finally``, and a sweeper removes leftovers of
crashed runs before and after the session.

    uv run pytest tests/live -v
"""

from __future__ import annotations

import json
import uuid
import re
from typing import Any

import pytest
from fastmcp import Client

from gcore_mcp_server.config.server_config import Mode, ServerConfig
from gcore_mcp_server.catalog import classify
from gcore_mcp_server.runtime.dispatch import call_tool_for
from gcore_mcp_server.runtime import SafetyPolicy
from gcore_mcp_server.server import create_server

from .common import (
    PREFIX,
    PROJECT_ID,
    REGION_ID,
    close_open_clients,
    live_client,
    sweep_leftovers,
    unique_name,
)
from .credentials import live_configured, restricted_api_key

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.live,
    pytest.mark.skipif(
        not live_configured(),
        reason="set GCORE_LIVE_API_KEY, GCORE_LIVE_PROJECT_ID and GCORE_LIVE_REGION_ID",
    ),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def close_clients() -> Any:
    yield
    await close_open_clients()


@pytest.fixture
async def sweep() -> Any:
    client = live_client()
    before = await sweep_leftovers(client)
    if before:
        print(f"swept leftovers before test: {before}")
    yield
    after = await sweep_leftovers(client)
    assert not after, f"test left resources behind (now removed): {after}"


def server(
    mode: Mode = Mode.DYNAMIC,
    policy: SafetyPolicy | None = None,
    api_key: str | None = None,
) -> Any:
    return create_server(
        ServerConfig(
            mode=mode, tools="cloud.ssh_keys.*" if mode is not Mode.DYNAMIC else None
        ),
        client=live_client(api_key),
        policy=policy or SafetyPolicy(),
    )


def text(res: Any) -> str:
    return res.content[0].text if res.content else ""


def payload(res: Any) -> Any:
    return json.loads(text(res))


async def call(
    client: Client, name: str, args: dict[str, Any] | None = None, **kw: Any
) -> Any:
    """The matching call tool, approving confirmations (the test is the user)."""
    tool = call_tool_for(classify(name))
    res = await client.call_tool(
        tool, {"name": name, "arguments": args or {}, **kw}, raise_on_error=False
    )
    if res.is_error and "CONFIRMATION REQUIRED" in text(res):
        token = re.search(r'confirm_token="([0-9a-f]+)"', text(res)).group(1)  # type: ignore[union-attr]
        res = await client.call_tool(
            tool,
            {"name": name, "arguments": args or {}, "confirm_token": token},
            raise_on_error=False,
        )
    assert not res.is_error, f"{name} failed: {text(res)[:800]}"
    return payload(res)


# ---------------------------------------------------------------- reads


async def test_discovery_to_call_on_real_account() -> None:
    async with Client(server()) as client:
        hits = payload(
            await client.call_tool("search_tools", {"query": "list regions"})
        )
        assert hits[0]["name"] == "cloud.regions.list"
        regions = await call(client, "cloud.regions.list")
        assert any(r["id"] == REGION_ID for r in regions["results"])
        projects = await call(client, "cloud.projects.list")
        assert any(p["id"] == PROJECT_ID for p in projects["results"])
        # Default project/region are injected.
        await call(client, "cloud.instances.list", {"limit": 5})


async def test_execute_code_aggregates_real_data() -> None:
    code = """
import asyncio
vols, nets = await asyncio.gather(call_tool('cloud.volumes.list'), call_tool('cloud.networks.list'))
unattached = [v['name'] for v in vols['results'] if not v.get('attachments')]
{'volumes': vols['count'], 'unattached': len(unattached), 'networks': nets['count']}
"""
    async with Client(server()) as client:
        res = await client.call_tool("execute_code", {"code": code})
    out = payload(res)
    assert out["api_calls"] == 2
    assert out["result"]["volumes"] >= out["result"]["unattached"] >= 0


async def test_not_found_is_explained() -> None:
    async with Client(server()) as client:
        res = await client.call_tool(
            "call_read_tool",
            {
                "name": "cloud.ssh_keys.get",
                "arguments": {"ssh_key_id": str(uuid.uuid4())},
            },
            raise_on_error=False,
        )
    assert res.is_error and "HTTP 404" in text(res) and "Hint" in text(res)


@pytest.mark.skipif(not restricted_api_key(), reason="no restricted key")
async def test_restricted_key_gets_a_permission_hint() -> None:
    """A key without the needed permissions must produce an actionable error."""
    async with Client(server(api_key=restricted_api_key())) as client:
        res = await client.call_tool(
            "call_write_tool",
            {
                "name": "cloud.ssh_keys.create",
                "arguments": {"name": unique_name("denied")},
            },
            raise_on_error=False,
        )
    if not res.is_error:
        # The restricted principal turned out to be allowed: clean up and say so.
        await sweep_leftovers(live_client())
        pytest.skip("restricted key is allowed to create SSH keys on this account")
    assert "HTTP 403" in text(res) or "HTTP 401" in text(res), text(res)
    assert "Hint" in text(res)


# ---------------------------------------------------------------- write lifecycles


async def test_ssh_key_lifecycle_with_confirmation(sweep: None) -> None:
    name = unique_name("key")
    async with Client(server()) as client:
        created = await call(client, "cloud.ssh_keys.create", {"name": name})
        key_id = created["id"]
        try:
            assert created["name"] == name and "private_key" in created
            got = await call(client, "cloud.ssh_keys.get", {"ssh_key_id": key_id})
            assert got["name"] == name
            # Delete needs confirmation: the first call must not delete.
            first = await client.call_tool(
                "call_destructive_tool",
                {"name": "cloud.ssh_keys.delete", "arguments": {"ssh_key_id": key_id}},
                raise_on_error=False,
            )
            assert first.is_error and "CONFIRMATION REQUIRED" in text(first)
            still = await call(client, "cloud.ssh_keys.get", {"ssh_key_id": key_id})
            assert still["id"] == key_id
        finally:
            await call(client, "cloud.ssh_keys.delete", {"ssh_key_id": key_id})
        gone = await client.call_tool(
            "call_read_tool",
            {"name": "cloud.ssh_keys.get", "arguments": {"ssh_key_id": key_id}},
            raise_on_error=False,
        )
        assert gone.is_error and "404" in text(gone)


async def test_direct_mode_ssh_key_lifecycle(sweep: None) -> None:
    name = unique_name("dkey")
    async with Client(server(Mode.DIRECT)) as client:
        created = payload(
            await client.call_tool("cloud_ssh_keys_create", {"name": name})
        )
        try:
            listed = payload(await client.call_tool("cloud_ssh_keys_list", {}))
            assert any(k["name"] == name for k in listed["results"])
        finally:
            first = await client.call_tool(
                "cloud_ssh_keys_delete",
                {"ssh_key_id": created["id"]},
                raise_on_error=False,
            )
            token = re.search(r'confirm_token="([0-9a-f]+)"', text(first)).group(1)  # type: ignore[union-attr]
            await client.call_tool(
                "cloud_ssh_keys_delete",
                {"ssh_key_id": created["id"], "confirm_token": token},
            )


async def test_security_group_lifecycle(sweep: None) -> None:
    name = unique_name("sg")
    async with Client(server()) as client:
        sg = await call(
            client,
            "cloud.security_groups.create_and_poll",
            {"name": name, "description": "mcp live test"},
        )
        try:
            rule = await call(
                client,
                "cloud.security_groups.rules.create_and_poll",
                {
                    "group_id": sg["id"],
                    "direction": "ingress",
                    "protocol": "tcp",
                    "port_range_min": 8443,
                    "port_range_max": 8443,
                    "ethertype": "IPv4",
                },
            )
            assert rule["direction"] == "ingress"
            got = await call(
                client, "cloud.security_groups.get", {"group_id": sg["id"]}
            )
            assert any(
                r.get("port_range_min") == 8443
                for r in got.get("security_group_rules", [])
            )
        finally:
            await call(client, "cloud.security_groups.delete", {"group_id": sg["id"]})


async def test_network_and_subnet_lifecycle_with_polling(sweep: None) -> None:
    name = unique_name("net")
    async with Client(server()) as client:
        net = await call(
            client,
            "cloud.networks.create_and_poll",
            {"name": name, "create_router": False},
        )
        try:
            assert net["name"] == name
            subnet = await call(
                client,
                "cloud.networks.subnets.create_and_poll",
                {
                    "name": name,
                    "network_id": net["id"],
                    "cidr": "192.168.77.0/24",
                    "connect_to_network_router": False,
                },
            )
            assert subnet["cidr"] == "192.168.77.0/24"
        finally:
            await call(
                client, "cloud.networks.delete_and_poll", {"network_id": net["id"]}
            )


async def test_volume_lifecycle(sweep: None) -> None:
    name = unique_name("vol")
    async with Client(server()) as client:
        vol = await call(
            client,
            "cloud.volumes.create_and_poll",
            {"name": name, "size": 1, "source": "new-volume", "type_name": "standard"},
        )
        try:
            assert vol["size"] == 1 and vol["name"] == name
            # A fresh unique name, so the sweeper still recognises the volume
            # if this run crashes after the rename.
            new_name = unique_name("vol")
            renamed = await call(
                client,
                "cloud.volumes.update",
                {"volume_id": vol["id"], "name": new_name},
            )
            assert renamed["name"] == new_name
        finally:
            await call(
                client, "cloud.volumes.delete_and_poll", {"volume_id": vol["id"]}
            )


async def test_dns_zone_and_record_lifecycle(sweep: None) -> None:
    zone = f"{unique_name('zone')}.com"
    async with Client(server()) as client:
        await call(client, "dns.zones.create", {"name": zone})
        try:
            await call(
                client,
                "dns.zones.rrsets.create",
                {
                    "zone_name": zone,
                    "rrset_name": f"www.{zone}",
                    "rrset_type": "A",
                    "resource_records": [{"content": ["192.0.2.10"]}],
                    "ttl": 300,
                },
            )
            rr = await call(
                client,
                "dns.zones.rrsets.get",
                {"zone_name": zone, "rrset_name": f"www.{zone}", "rrset_type": "A"},
            )
            assert "192.0.2.10" in json.dumps(rr)
        finally:
            await call(client, "dns.zones.delete", {"name": zone})


async def test_read_only_mode_blocks_real_writes() -> None:
    async with Client(server(policy=SafetyPolicy(read_only=True))) as client:
        res = await client.call_tool(
            "call_read_tool",  # the only call tool in read-only mode
            {"name": "cloud.ssh_keys.create", "arguments": {"name": unique_name("ro")}},
            raise_on_error=False,
        )
        listed = await call(client, "cloud.ssh_keys.list")
    assert res.is_error and "read-only" in text(res)
    assert not any(k["name"].startswith(PREFIX + "ro") for k in listed["results"])

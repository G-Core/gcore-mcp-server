"""Shared setup for tests against a real Gcore account.

Safety rules for everything under tests/live:

* Every resource created gets a name from :func:`unique_name`:
  ``mcp-test-<kind>-<unix time><3 random digits>``.
* Cleanup runs in ``finally``. ``sweep_leftovers`` deletes ``mcp-test-*``
  resources this process created, plus those of crashed runs (older than
  ``STALE_AFTER_SECS``). It never touches another session's live resources or
  anything without the prefix.
* Only cheap resources (SSH keys, security groups, networks, 1 GB volumes,
  DNS zones). No instances, bare metal or GPUs.
"""

from __future__ import annotations

import re
import secrets
import time
from typing import Any

import gcore

from gcore_mcp_server.catalog import Catalog
from gcore_mcp_server.runtime import ConfirmMode, Dispatcher, SafetyPolicy

from .credentials import live_api_key, live_location

PREFIX = "mcp-test-"
# 0 when unset; live tests skip in that case (see credentials.live_configured).
PROJECT_ID, REGION_ID = live_location() or (0, 0)


STALE_AFTER_SECS = 2 * 3600
_OWNED: set[str] = set()
_STAMP = re.compile(r"-(\d{10})\d{3}$")


def unique_name(kind: str) -> str:
    """A resource name owned by this process (see :func:`sweep_leftovers`)."""
    name = f"{PREFIX}{kind}-{int(time.time())}{secrets.randbelow(1000):03d}"
    _OWNED.add(name)
    return name


def _sweepable(name: str) -> bool:
    """Ours, or left by a run that started long enough ago to have crashed."""
    base = name.split(".", 1)[0]  # DNS zones are "<name>.com"
    if not base.startswith(PREFIX):
        return False
    if base in _OWNED:
        return True
    stamp = _STAMP.search(base)
    return bool(stamp) and time.time() - int(stamp.group(1)) > STALE_AFTER_SECS


# Clients created during a test; closed by the ``close_clients`` fixture so no
# connection outlives the event loop it was opened on.
OPEN_CLIENTS: list[Any] = []


def live_client(api_key: str | None = None) -> Any:
    key = api_key or live_api_key()
    if not key:
        raise RuntimeError("no live API key")
    client = gcore.AsyncGcore(
        api_key=key, cloud_project_id=PROJECT_ID, cloud_region_id=REGION_ID, timeout=60
    )
    OPEN_CLIENTS.append(client)
    return client


async def close_open_clients() -> None:
    while OPEN_CLIENTS:
        await OPEN_CLIENTS.pop().close()


def unguarded_dispatcher(client: Any) -> Dispatcher:
    """Dispatcher without confirmations, for cleanup code only."""
    return Dispatcher(
        Catalog.from_client(client), SafetyPolicy(confirm=ConfirmMode.NONE)
    )


async def sweep_leftovers(client: Any) -> list[str]:
    """Delete this run's and crashed runs' ``mcp-test-*`` resources; return them."""
    removed: list[str] = []

    async def each(paginator: Any) -> list[Any]:
        """Every item on every page, read before anything is deleted (deleting
        while paging would shift the offsets still to be read)."""
        return [item async for item in paginator]

    async def gone(label: str, coro: Any) -> None:
        """Run a delete; a 404 means it is already gone (listings lag deletes)."""
        try:
            await coro
            removed.append(label)
        except gcore.NotFoundError:
            pass

    for key in await each(client.cloud.ssh_keys.list(limit=1000)):
        if _sweepable(key.name):
            await gone(
                f"ssh_key {key.name}", client.cloud.ssh_keys.delete(ssh_key_id=key.id)
            )
    for sg in await each(client.cloud.security_groups.list(limit=1000)):
        if _sweepable(sg.name):
            await gone(
                f"security_group {sg.name}",
                client.cloud.security_groups.delete(group_id=sg.id),
            )
    for vol in await each(client.cloud.volumes.list(limit=1000)):
        if _sweepable(vol.name or "") and vol.status == "available":
            await gone(
                f"volume {vol.name}",
                client.cloud.volumes.delete_and_poll(volume_id=vol.id),
            )
    for net in await each(client.cloud.networks.list(limit=1000)):
        if _sweepable(net.name):
            await gone(
                f"network {net.name}",
                client.cloud.networks.delete_and_poll(network_id=net.id),
            )
    for zone in await each(client.dns.zones.list(limit=1000)):
        if _sweepable(zone.name or ""):
            await gone(f"dns_zone {zone.name}", client.dns.zones.delete(name=zone.name))
    return removed

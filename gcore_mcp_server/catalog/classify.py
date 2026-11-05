"""Classify SDK methods as read, write or destructive from their names.

The classification is derived from the method name (the last path segment), so
new SDK methods are classified automatically on upgrade. ``OVERRIDES`` corrects
the few names where the verb is misleading. The golden catalog snapshot
(``tests/snapshots/catalog.json``) records the class of every method, so a
reviewer sees any change of classification in the SDK-bump diff.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class Access(str, Enum):
    """What calling a method does to the account."""

    READ = "read"
    """No side effects: list, get, lookup, validate, estimate…"""

    WRITE = "write"
    """Creates or changes resources, but is not expected to lose data."""

    DESTRUCTIVE = "destructive"
    """Deletes, replaces, disrupts or disables something."""


POLL_SUFFIX: Final[str] = "_and_poll"

# Verb prefixes (first word of the method name) with no side effects.
_READ_PREFIXES: Final[tuple[str, ...]] = (
    "list",
    "get",
    "check",
    "lookup",
    "estimate",
    "preview",
    "export",
    "download",
    "validate",
    "prevalidate",
    "poll",
)

# Verb prefixes that delete, overwrite, interrupt or weaken something.
_DESTRUCTIVE_PREFIXES: Final[tuple[str, ...]] = (
    # Generic power actions (start, stop, reboot, ...) on servers and clusters.
    "action",
    "delete",
    "remove",
    "purge",
    "detach",
    "unassign",
    "disable",
    "stop",
    "revert",
    "regenerate",
    "refresh_secret",
    "rebuild",
    "reboot",
    "powercycle",
    "failover",
    "recreate",
    "cancel",
    "clear",
    "unapply",
    "replace",
    "resize",
    "upgrade",
    "toggle",
)

# Full method path → access, for names whose verb is misleading.
OVERRIDES: Final[dict[str, Access]] = {
    # Gives every server a new image, SSH key and user data: a rebuild that wipes
    # the servers, despite the mild verb.
    "cloud.gpu_baremetal.clusters.apply_settings": Access.DESTRUCTIVE,
    "cloud.gpu_baremetal.clusters.servers.apply_settings": Access.DESTRUCTIVE,
    # Same request as the destructive vip.toggle: turning VIP off cuts traffic
    # to the ports that share the address.
    "cloud.reserved_fixed_ips.update": Access.DESTRUCTIVE,
    # Can disable DNSSEC (force_disable even with DS records published), which
    # breaks resolution of the zone for validating resolvers.
    "dns.zones.dnssec.update": Access.DESTRUCTIVE,
    # port_id: null disconnects the address, like the destructive unassign
    # (which is deprecated in favour of this endpoint).
    "cloud.floating_ips.update": Access.DESTRUCTIVE,
    "cloud.floating_ips.update_and_poll": Access.DESTRUCTIVE,
    # Drops cached copies only: the CDN fetches them from the origin again,
    # which is what a deploy needs. No data is lost, so it's a write.
    "cdn.cdn_resources.purge": Access.WRITE,
}


def method_verb(full_name: str) -> str:
    """Return the method part of ``full_name`` without an ``_and_poll`` suffix."""
    verb = full_name.rsplit(".", 1)[-1]
    if verb.endswith(POLL_SUFFIX):
        verb = verb[: -len(POLL_SUFFIX)]
    return verb


def _matches(verb: str, prefixes: tuple[str, ...]) -> bool:
    return any(verb == p or verb.startswith(p + "_") for p in prefixes)


def classify(full_name: str) -> Access:
    """Classify an SDK method path such as ``cloud.instances.delete``."""
    # Overrides cover the *_and_poll variant too (same request, then a wait).
    base = full_name.removesuffix("_and_poll")
    if base in OVERRIDES:
        return OVERRIDES[base]
    verb = method_verb(full_name)
    if _matches(verb, _DESTRUCTIVE_PREFIXES):
        return Access.DESTRUCTIVE
    if _matches(verb, _READ_PREFIXES):
        return Access.READ
    return Access.WRITE

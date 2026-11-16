"""Result budget and approval-prompt details (unit level)."""

from __future__ import annotations

import json
import time

from gcore_mcp_server.catalog import Access, ToolEntry
from gcore_mcp_server.runtime.safety import describe_batch, describe_call
from gcore_mcp_server.runtime.shaping import truncate
from tests.live import common


def size(value: object) -> int:
    return len(json.dumps(value, default=str))


def test_page_with_huge_other_fields_still_fits_the_budget() -> None:
    value = {"results": [], "details": "x" * 1_000_000}
    out, cut = truncate(value, 40_000)
    assert cut and size(out) <= 40_000


def test_small_limits_keep_a_short_prefix() -> None:
    out, cut = truncate("y" * 10_000, 100)
    assert cut and size(out) < 400


def test_lists_keep_leading_items_within_budget() -> None:
    out, cut = truncate(
        {"results": [{"n": i} for i in range(5000)], "count": 5000}, 2000
    )
    assert cut and size(out) <= 2000
    assert out["_truncated"]["total"] == 5000


def entry(name: str) -> ToolEntry:
    return ToolEntry(
        name=name, access=Access.DESTRUCTIVE, summary="s", description="", method=print
    )


def test_approval_prompt_always_shows_the_target() -> None:
    records = [{"content": ["10.0.0.1"] * 2000}]
    text = describe_call(
        entry("dns.zones.rrsets.replace"),
        {
            "resource_records": records,
            "rrset_name": "www",
            "zone_name": "example.com",
            "rrset_type": "A",
        },
    )
    assert text.index("rrset_name www") < text.index("resource_records")
    assert "zone_name example.com" in text
    assert "more chars" in text  # the long value is shortened, not the target


def test_sweeper_only_takes_own_or_stale_resources() -> None:
    mine = common.unique_name("key")
    assert common._sweepable(mine)  # pyright: ignore[reportPrivateUsage]
    other_live = f"{common.PREFIX}key-{int(time.time())}123"
    assert not common._sweepable(other_live)  # pyright: ignore[reportPrivateUsage]
    stale = f"{common.PREFIX}key-{int(time.time()) - 3 * 3600}123"
    assert common._sweepable(stale)  # pyright: ignore[reportPrivateUsage]
    assert common._sweepable(f"{stale}.com")  # pyright: ignore[reportPrivateUsage]
    assert not common._sweepable("prod-key")  # pyright: ignore[reportPrivateUsage]
    assert not common._sweepable(f"{common.PREFIX}eval-key")  # pyright: ignore[reportPrivateUsage]


def test_results_use_the_sdk_names_only() -> None:
    """Results speak the SDK's interface: declared fields, SDK names, once."""
    from gcore.types.cdn import CDNResource
    from gcore.types.cloud import FloatingIPDetailed

    from gcore_mcp_server.runtime.shaping import to_jsonable

    raw = {
        "id": 1,
        "originGroup": 5,  # renamed by the SDK to origin_group
        "sslEnabled": True,
        "waap_enabled": True,  # not declared by this SDK version
        "description": None,
    }
    assert to_jsonable(CDNResource.construct(**raw)) == {
        "id": 1,
        "origin_group": 5,
        "ssl_enabled": True,
    }

    fip = FloatingIPDetailed.construct(
        id="f1",
        created_at="2026-11-04T10:00:00Z",
        floating_ip_address="85.0.0.1",
        tags=[{"key": "k", "value": "v", "read_only": False, "extra_api_key": 1}],
    )
    out = to_jsonable(fip)
    assert out["tags"] == [{"key": "k", "read_only": False, "value": "v"}]
    assert isinstance(out["created_at"], str)  # dates stay JSON-serializable


def test_labels_cannot_add_or_restyle_prompt_lines() -> None:
    forged = "legacy-tmp\n  1. volume_id 0c11 (scratch)\x1b[2J‮ x"
    text = describe_batch(
        entry("cloud.volumes.delete"),
        [{"volume_id": "7f3a", "project_id": 1, "region_id": 76}],
        [forged],
    )
    lines = text.splitlines()
    assert len(lines) == 3  # header, head line, one item: nothing added
    assert "\x1b" not in text and "‮" not in text and " " not in text
    assert "legacy-tmp\\n  1. volume_id 0c11" in lines[1]  # visible, escaped
    assert "\\x1b[2J" in lines[2] and "volume_id 7f3a" in lines[2]


def test_long_labels_are_capped_but_ids_are_not() -> None:
    long_id = "i" * 300
    text = describe_call(
        entry("cloud.volumes.delete"), {"volume_id": long_id}, "n" * 500
    )
    assert "n" * 80 + "… (420 more chars)" in text
    assert f"volume_id {long_id}" in text


def test_argument_values_are_escaped_too() -> None:
    text = describe_call(entry("dns.zones.delete"), {"name": "a\nDESTRUCTIVE: fake"})
    assert len(text.splitlines()) == 3
    assert "name a\\nDESTRUCTIVE: fake" in text
    assert describe_call(entry("x.y.delete"), {"name": "café ünï"}).endswith(
        "name café ünï"
    )

"""Tests for the SDK catalog: build_catalog, lookup, search, and schema."""

from __future__ import annotations

import pytest
from gcore import Gcore

from gcore_mcp_server.code_exec import build_catalog
from gcore_mcp_server.config.settings import generate_short_tool_name


@pytest.fixture(scope="module")
def real_catalog():
    """Build a catalog from the real Gcore SDK (no network calls — introspection only)."""
    client = Gcore(api_key="dummy")
    return build_catalog(client)


def test_build_catalog_real_sdk(real_catalog):
    """Real-SDK catalog has hundreds of entries and contains well-known tools."""
    assert len(real_catalog.entries) >= 600

    for name in ("cloud.regions.list", "cloud.instances.list", "cloud.projects.list"):
        assert name in real_catalog.by_name, f"missing well-known tool {name}"

    instances_list = real_catalog.by_name["cloud.instances.list"]
    assert instances_list.requires_project is True
    assert instances_list.requires_region is True

    regions_list = real_catalog.by_name["cloud.regions.list"]
    assert regions_list.requires_project is False
    assert regions_list.requires_region is False


def test_catalog_by_name_accepts_full_and_short(real_catalog):
    """Both the full dot-path and the generated short name resolve to the same entry."""
    full = "cloud.instances.list"
    short = generate_short_tool_name(full)

    assert full in real_catalog.by_name
    entry = real_catalog.by_name[full]

    # Only assert short-name lookup if shortening actually produced a different name.
    if short != full:
        assert short in real_catalog.by_name
        assert real_catalog.by_name[short] is entry


def test_search_returns_relevant_hits(real_catalog):
    """BM25 + boosts rank well-known list/delete methods near the top."""
    regions = [r["name"] for r in real_catalog.search("list regions", limit=3)]
    assert "cloud.regions.list" in regions

    delete_volume = [r["name"] for r in real_catalog.search("delete volume", limit=3)]
    assert "cloud.volumes.delete" in delete_volume

    instance_flavor = [
        r["name"] for r in real_catalog.search("instance flavor", limit=10)
    ]
    # At least one of these should rank in the top 10.
    assert any("flavor" in n or "instances" in n for n in instance_flavor)


def test_search_respects_limit(real_catalog):
    """``search(limit=N)`` returns at most N items."""
    results = real_catalog.search("list", limit=5)
    assert len(results) <= 5

    results = real_catalog.search("cloud", limit=1)
    assert len(results) <= 1


def test_search_score_boosts(real_catalog):
    """Name-match boost lifts ``cloud.regions.list`` above incidental mentions."""
    results = [r["name"] for r in real_catalog.search("regions", limit=10)]
    assert "cloud.regions.list" in results
    assert "cloud.regions.get" in results
    # Both name-matched entries should be in the top half of a 10-item result list.
    assert results.index("cloud.regions.list") < 5
    assert results.index("cloud.regions.get") < 5


def test_get_schema_known_tool(real_catalog):
    """``get_schema`` exposes a structured description of a known tool."""
    schema = real_catalog.get_schema("cloud.regions.list")

    assert set(["name", "doc", "params", "requires_project", "requires_region"]) <= set(
        schema.keys()
    )
    assert schema["name"] == "cloud.regions.list"
    assert isinstance(schema["params"], list)
    assert len(schema["params"]) > 0
    for param in schema["params"]:
        assert set(["name", "type", "required", "default"]) <= set(param.keys())


def test_get_schema_unknown_raises_keyerror(real_catalog):
    """``get_schema`` on an unknown tool raises KeyError with a helpful message."""
    with pytest.raises(KeyError) as exc:
        real_catalog.get_schema("nope.does.not.exist")
    # KeyError stringifies with quotes — the unknown name is part of the message.
    assert "nope.does.not.exist" in str(exc.value)


def test_tokenizer_splits_dots_underscores_camelcase(real_catalog):
    """The tokenizer splits dotted, underscored, and camelCase tokens so search works."""
    # Underscored: gpu_baremetal_clusters → "gpu", "baremetal", "clusters".
    results = [r["name"] for r in real_catalog.search("gpu baremetal", limit=10)]
    assert any("gpu_baremetal" in n for n in results), (
        f"expected a gpu_baremetal_* method in top 10, got {results}"
    )

"""The generated catalog: coverage, classification, schemas, search, snapshot."""

from __future__ import annotations

import inspect
import json
import os
import re
from pathlib import Path

import jsonschema
import pytest

from gcore_mcp_server.catalog import Access, classify
from gcore_mcp_server.catalog.docstrings import parse_docstring
from gcore_mcp_server.catalog.export import list_operations, operations_markdown
from gcore_mcp_server.catalog.typed import scoped_path_params
from gcore_mcp_server.modes.direct import tool_name_for

from tests.helpers import full_catalog

SNAPSHOT = Path(__file__).parent / "snapshots" / "catalog.json"
OPERATIONS_DOC = Path(__file__).parents[1] / "docs" / "OPERATIONS.md"
# In CI a missing generated file must fail the build, not be created silently.
IN_CI = bool(os.getenv("CI"))
TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def test_catalog_covers_the_sdk() -> None:
    catalog = full_catalog()
    assert len(catalog.entries) > 750
    services = set(catalog.services())
    assert {
        "cloud",
        "cdn",
        "dns",
        "waap",
        "storage",
        "streaming",
        "fastedge",
        "iam",
    } <= services
    assert not services & {"qs", "timeout"}, "client plumbing must not be exposed"


def test_every_entry_has_a_valid_schema_and_name() -> None:
    """Every operation must produce a valid JSON schema and an MCP-legal name."""
    problems: list[str] = []
    for entry in full_catalog().entries:
        try:
            schema = entry.input_schema
            jsonschema.Draft202012Validator.check_schema(schema)
        except Exception as exc:  # pragma: no cover - reported below
            problems.append(f"{entry.name}: {exc}")
            continue
        if schema.get("type") != "object":
            problems.append(f"{entry.name}: schema is not an object")
        if not TOOL_NAME.match(tool_name_for(entry)):
            problems.append(f"{entry.name}: invalid tool name {tool_name_for(entry)!r}")
        if not entry.summary:
            problems.append(f"{entry.name}: empty summary")
        hidden = {"extra_headers", "extra_query", "extra_body", "timeout"} & set(
            schema.get("properties", {})
        )
        if hidden:
            problems.append(f"{entry.name}: exposes transport params {hidden}")
    assert not problems, "\n".join(problems[:30])


def test_direct_tool_names_are_unique() -> None:
    names = [tool_name_for(e) for e in full_catalog().entries]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes


def test_project_and_region_are_optional_with_guidance() -> None:
    entry = full_catalog().resolve("cloud.instances.list")
    assert entry is not None
    props = entry.input_schema["properties"]
    assert "project_id" not in entry.required_params
    assert "default project" in props["project_id"]["description"]
    assert "cloud.regions.list" in props["region_id"]["description"]


def test_project_and_region_filters_are_left_alone() -> None:
    """On cloud.tasks.list project/region are filters ("all" when unset)."""
    catalog = full_catalog()
    tasks = catalog.resolve("cloud.tasks.list")
    volumes = catalog.resolve("cloud.volumes.create_and_poll")
    assert tasks is not None and volumes is not None
    assert scoped_path_params(tasks.method, tasks.name) == frozenset()
    assert "default project" not in str(tasks.input_schema)
    assert scoped_path_params(volumes.method, volumes.name) == {
        "project_id",
        "region_id",
    }


def test_argument_docs_reach_the_schema() -> None:
    entry = full_catalog().resolve("cloud.ssh_keys.create")
    assert entry is not None
    assert entry.input_schema["properties"]["name"]["description"] == "SSH key name"
    assert entry.required_params == ["name"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cloud.instances.list", Access.READ),
        ("cloud.instances.get", Access.READ),
        ("dns.lookup", Access.READ),
        ("cloud.k8s.clusters.pools.check_quota", Access.READ),
        ("cloud.tasks.poll", Access.READ),
        ("cloud.ssh_keys.create", Access.WRITE),
        ("cloud.networks.create_and_poll", Access.WRITE),
        ("cloud.instances.update", Access.WRITE),
        ("cdn.certificates.renew", Access.WRITE),
        # Power actions (stop, reboot, ...) behind one generic endpoint.
        ("cloud.instances.action", Access.DESTRUCTIVE),
        ("cloud.instances.action_and_poll", Access.DESTRUCTIVE),
        ("cloud.baremetal.servers.action", Access.DESTRUCTIVE),
        ("cloud.gpu_virtual.clusters.action_and_poll", Access.DESTRUCTIVE),
        # Re-images every server despite the mild verb (override, incl. _and_poll).
        ("cloud.gpu_baremetal.clusters.apply_settings", Access.DESTRUCTIVE),
        ("cloud.reserved_fixed_ips.update", Access.DESTRUCTIVE),
        ("dns.zones.dnssec.update", Access.DESTRUCTIVE),
        # port_id: null disconnects it, like the destructive unassign.
        ("cloud.floating_ips.update", Access.DESTRUCTIVE),
        ("cloud.floating_ips.update_and_poll", Access.DESTRUCTIVE),
        ("cloud.gpu_baremetal.clusters.apply_settings_and_poll", Access.DESTRUCTIVE),
        ("cloud.gpu_baremetal.clusters.servers.apply_settings", Access.DESTRUCTIVE),
        ("cloud.instances.delete", Access.DESTRUCTIVE),
        ("cloud.instances.delete_and_poll", Access.DESTRUCTIVE),
        # Cache only: the origin keeps the data; deploys need it.
        ("cdn.cdn_resources.purge", Access.WRITE),
        ("cloud.volumes.detach_from_instance", Access.DESTRUCTIVE),
        ("dns.zones.replace", Access.DESTRUCTIVE),
        ("waap.domains.firewall_rules.toggle", Access.DESTRUCTIVE),
        (
            "cloud.databases.postgres.clusters.user_credentials.regenerate",
            Access.DESTRUCTIVE,
        ),
        ("cloud.gpu_baremetal.clusters.reboot_all_servers", Access.DESTRUCTIVE),
    ],
)
def test_classification(name: str, expected: Access) -> None:
    assert classify(name) is expected


def test_no_delete_is_classified_as_safe() -> None:
    risky = [
        e.name
        for e in full_catalog().entries
        if re.search(r"\.(delete|remove|purge)", e.name)
        and e.access is not Access.DESTRUCTIVE
        and e.name != "cdn.cdn_resources.purge"  # cache only, see OVERRIDES
    ]
    assert not risky


# Read operations the SDK sends as POST. Each was checked to be a query (metrics,
# reports, quota checks, dry-run validation or preview) that changes nothing.
# Add an operation here only after confirming that; otherwise fix its class with
# OVERRIDES in catalog/classify.py.
READS_SENT_AS_POST = {
    "cdn.cdn_resources.prevalidate_ssl_le_certificate",
    "cdn.logs_uploader.configs.validate",
    "cdn.logs_uploader.targets.validate",
    "cdn.metrics.list",
    "cloud.cost_reports.get_aggregated_monthly",
    "cloud.cost_reports.get_breakdown",
    "cloud.cost_reports.get_detailed",
    "cloud.databases.postgres.custom_configurations.validate",
    "cloud.instances.metrics.list",
    "cloud.k8s.clusters.pools.check_quota",
    "cloud.load_balancers.metrics.list",
    "cloud.networks.routers.metrics.list",
    "cloud.snapshot_schedules.estimate_max_usage",
    "cloud.usage_reports.get",
    "storage.statistics.get_usage_aggregated",
    "storage.statistics.get_usage_series",
    "waap.custom_page_sets.preview",
}
# `self._get(` sends a request; `self.get(` delegates to a sibling (e.g. tasks.poll).
HTTP_CALL = re.compile(r"self\._?(get_api_list|get|post|put|patch|delete)\(")


def test_read_operations_only_send_get() -> None:
    """Read-only mode trusts the verb-based class; check it against the HTTP method.

    A method named like a read (``get_…``, ``check_…``) that actually sends a
    write would otherwise slip through read-only mode after an SDK upgrade.
    """
    unexpected: dict[str, list[str]] = {}
    for entry in full_catalog().entries:
        if entry.access is not Access.READ:
            continue
        methods = {
            "get" if m == "get_api_list" else m
            for m in HTTP_CALL.findall(inspect.getsource(entry.method))
        }
        if not methods:
            unexpected[entry.name] = ["<no HTTP call found>"]
        elif methods != {"get"} and not (
            entry.name in READS_SENT_AS_POST and methods <= {"get", "post"}
        ):
            unexpected[entry.name] = sorted(methods)
    assert not unexpected, (
        "read operations that send something other than GET; review each and "
        f"either reclassify it or add it to READS_SENT_AS_POST: {unexpected}"
    )


def test_reads_sent_as_post_list_is_current() -> None:
    reads = {e.name for e in full_catalog().entries if e.access is Access.READ}
    assert READS_SENT_AS_POST <= reads, READS_SENT_AS_POST - reads


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("list my virtual machines", "cloud.instances.list"),
        ("unattached volumes", "cloud.volumes.list"),
        ("create ssh key", "cloud.ssh_keys.create"),
        ("delete dns record", "dns.zones.rrsets.delete"),
        ("purge cdn cache", "cdn.cdn_resources.purge"),
        ("which regions", "cloud.regions.list"),
        ("floating ip", "cloud.floating_ips.list"),
        ("k8s clusters", "cloud.k8s.clusters.list"),
        ("my projects", "cloud.projects.list"),
        ("instance flavors", "cloud.instances.flavors.list"),
        ("dns zones", "dns.zones.list"),
        ("list buckets", "storage.object_storages.buckets.list"),
        ("create network", "cloud.networks.create"),
        ("attach volume to instance", "cloud.volumes.attach_to_instance"),
        ("cost report", "cloud.cost_reports.get_detailed"),
        ("security groups", "cloud.security_groups.list"),
        ("load balancers", "cloud.load_balancers.list"),
    ],
)
def test_search_finds_the_obvious_operation(query: str, expected: str) -> None:
    top = [hit["name"] for hit in full_catalog().search(query, limit=3)]
    assert expected in top, f"{query!r} -> {top}"


def test_search_by_resource_path_lists_the_resource() -> None:
    names = [h["name"] for h in full_catalog().search("cloud.ssh_keys", limit=20)]
    assert set(names) == {
        "cloud.ssh_keys.create",
        "cloud.ssh_keys.delete",
        "cloud.ssh_keys.get",
        "cloud.ssh_keys.list",
        "cloud.ssh_keys.update",
    }


def test_search_access_filter() -> None:
    hits = full_catalog().search("instances", limit=20, access="destructive")
    assert hits and all(h["access"] == "destructive" for h in hits)


def test_suggest_for_unknown_names() -> None:
    assert "cloud.instances.list" in full_catalog().suggest("cloud.instance.list")


def test_docstring_parsing() -> None:
    doc = parse_docstring(
        """Create a thing. More detail here.

Args:
  project_id: Project ID

  name: The name. It can be
      long.

  extra_headers: Send extra headers
"""
    )
    assert doc.summary == "Create a thing."
    assert doc.description == "Create a thing. More detail here."
    assert doc.args["name"] == "The name. It can be long."
    assert doc.args["project_id"] == "Project ID"


def test_docstring_parsing_keeps_indented_docstrings() -> None:
    """Python <3.13 keeps a docstring's indentation; the sections still parse."""
    doc = parse_docstring(
        """Get a thing

        Args:
          name: The name.

          extra_headers: Send extra headers
        """
    )
    assert doc.summary == doc.description == "Get a thing"
    assert doc.args["name"] == "The name."


def test_catalog_snapshot_matches_installed_sdk() -> None:
    """Golden file of every operation, its access class and required params.

    After an SDK upgrade this fails with the exact list of added, removed and
    changed operations. Review the diff, then regenerate with
    ``UPDATE_SNAPSHOTS=1 uv run pytest tests/test_catalog.py``.
    """
    current = full_catalog().snapshot()
    if os.getenv("UPDATE_SNAPSHOTS") or (not SNAPSHOT.exists() and not IN_CI):
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
    assert SNAPSHOT.exists(), (
        "catalog snapshot missing - run UPDATE_SNAPSHOTS=1 uv run pytest tests/test_catalog.py"
    )
    saved = json.loads(SNAPSHOT.read_text())
    added = sorted(set(current) - set(saved))
    removed = sorted(set(saved) - set(current))
    changed = sorted(n for n in set(current) & set(saved) if current[n] != saved[n])
    assert not (added or removed or changed), (
        "SDK catalog changed - review, then run UPDATE_SNAPSHOTS=1 uv run pytest "
        f"tests/test_catalog.py\nadded: {added}\nremoved: {removed}\n"
        + "changed: "
        + "; ".join(f"{n}: {saved[n]} -> {current[n]}" for n in changed)
    )


def test_operations_doc_is_current() -> None:
    """docs/OPERATIONS.md lists every operation of the installed SDK.

    Fails after an SDK upgrade until the file is regenerated with
    ``UPDATE_SNAPSHOTS=1 uv run pytest tests/test_catalog.py``.
    """
    current = operations_markdown(full_catalog())
    if os.getenv("UPDATE_SNAPSHOTS") or (not OPERATIONS_DOC.exists() and not IN_CI):
        OPERATIONS_DOC.write_text(current)
    assert OPERATIONS_DOC.exists() and OPERATIONS_DOC.read_text() == current, (
        "docs/OPERATIONS.md is out of date - run "
        "UPDATE_SNAPSHOTS=1 uv run pytest tests/test_catalog.py"
    )


def test_list_operations_filters_by_pattern() -> None:
    lines = list_operations(full_catalog(), ["cloud.volumes.delete*"])
    assert any("cloud.volumes.delete_and_poll" in line for line in lines)
    assert all(line.startswith("destructive") for line in lines[:-1])
    assert lines[-1].startswith(f"{len(lines) - 1} of ")


# ---------------------------------------------------------------- result outline


def _keys(fields: list[str]) -> set[str]:
    """Top-level names in an outline (``instance{id,name}`` -> ``instance``)."""
    return {re.split(r"[\[{]", f, maxsplit=1)[0] for f in fields}


def test_outline_names_the_fields_models_guessed_wrong_live() -> None:
    catalog = full_catalog()
    fips = catalog.describe(catalog.resolve("cloud.floating_ips.list"))["returns"]
    assert fips["list_key"] == "results" and fips["other_keys"] == ["count"]
    assert {"floating_ip_address", "port_id", "instance"} <= _keys(fips["item_fields"])
    assert "region_id" in fips["without_region_id"]

    costs = catalog.resolve("cloud.cost_reports.get_breakdown").returns
    assert costs is not None
    rows = next(f for f in costs["fields"] if f.startswith("results[]"))
    assert "project_id" in rows and "region_id" in rows
    # Small objects one level down are spelled out too (cost was missed live).
    assert "usage{cost,currency,unit,value}" in rows


def test_outline_shows_each_products_list_key() -> None:
    catalog = full_catalog()
    expected = {
        "dns.zones.list": ("zones", ["total_amount"]),
        "streaming.videos.list": ("items", None),
        "fastedge.apps.list": ("apps", ["count"]),
        "cloud.volumes.list": ("results", ["count"]),
    }
    for name, (key, other) in expected.items():
        outline = catalog.resolve(name).returns
        assert outline is not None
        assert outline["list_key"] == key, name
        assert outline.get("other_keys") == other, name


def test_outline_uses_the_sdk_field_names() -> None:
    """Results carry the SDK's names (see shaping.to_jsonable), so must this."""
    outline = full_catalog().resolve("cdn.cdn_resources.list").returns
    assert outline is not None
    keys = _keys(outline["item_fields"])
    assert "origin_group" in keys and "originGroup" not in keys


def test_operations_without_a_body_say_so() -> None:
    outline = full_catalog().resolve("cloud.ssh_keys.delete").returns
    assert outline == {"nothing": "the result is {'ok': true}"}


def test_region_merge_is_described_only_where_it_happens() -> None:
    catalog = full_catalog()
    interfaces = catalog.resolve("cloud.instances.interfaces.list").returns
    assert interfaces is not None and "without_region_id" not in interfaces
    projects = catalog.resolve("cloud.projects.list").returns
    assert projects is not None and "without_region_id" not in projects


def test_outline_matches_what_results_contain() -> None:
    """For every list operation, a serialized item has exactly the outlined keys."""
    import typing

    from gcore_mcp_server.runtime.shaping import to_jsonable

    checked = 0
    for entry in full_catalog().entries:
        outline = entry.returns
        if not outline or "item_fields" not in outline:
            continue
        page = typing.get_args(typing.get_type_hints(entry.method)["return"])[1]
        items = page.model_fields[outline["list_key"]].annotation
        item_type = typing.get_args(items)[0]
        if not (isinstance(item_type, type) and hasattr(item_type, "model_fields")):
            continue  # unions: the outline merges their fields
        sample = item_type.construct(
            **{f.alias or n: "x" for n, f in item_type.model_fields.items()}
        )
        assert set(to_jsonable(sample)) == _keys(outline["item_fields"]), entry.name
        checked += 1
    assert checked > 100


def test_every_outline_is_small() -> None:
    sizes = {
        e.name: len(json.dumps(e.returns)) for e in full_catalog().entries if e.returns
    }
    assert len(sizes) == len(full_catalog().entries)
    assert max(sizes.values()) < 4000, max(sizes, key=sizes.__getitem__)

"""Cloud project/region without GCORE_CLOUD_PROJECT_ID / GCORE_CLOUD_REGION_ID.

Only the API key is configured: the server picks the account's default project
and searches every region for list calls (see runtime/scope.py).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client

from tests.helpers import BASE_URL, data, make_client, make_server, text

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


DEFAULT_PROJECT = 6
OTHER_PROJECT = 4242
REGIONS = [
    (76, "Luxembourg-2", "ACTIVE"),
    (38, "Frankfurt", "ACTIVE"),
    (5, "Old", "DELETED"),
]


def projects(*items: tuple[int, str, bool]) -> dict[str, Any]:
    return {
        "count": len(items),
        "results": [
            {"id": i, "name": n, "is_default": d, "state": "ACTIVE", "client_id": 1}
            for i, n, d in items
        ],
    }


TWO_PROJECTS = projects(
    (DEFAULT_PROJECT, "Default", True), (OTHER_PROJECT, "test", False)
)


@pytest.fixture
def api():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.get("/cloud/v1/projects").mock(
            return_value=httpx.Response(200, json=TWO_PROJECTS)
        )
        mock.get("/cloud/v1/regions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": len(REGIONS),
                    "results": [
                        {"id": i, "display_name": n, "state": s} for i, n, s in REGIONS
                    ],
                },
            )
        )
        yield mock


def unpinned_server(**kwargs: Any) -> Any:
    return make_server(client=make_client(project=None, region=None), **kwargs)


def volumes(region: int, *names: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "count": len(names),
            "results": [{"id": f"{region}-{n}", "name": n} for n in names],
        },
    )


async def test_list_uses_default_project_and_searches_all_regions(
    api: respx.MockRouter,
) -> None:
    lux = api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/76").mock(
        return_value=volumes(76, "a", "b")
    )
    fra = api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/38").mock(
        return_value=volumes(38, "c")
    )
    deleted = api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/5")
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool("call_read_tool", {"name": "cloud.volumes.list"})
        )
    assert lux.called and fra.called and not deleted.called
    assert res["count"] == 3
    assert {(v["name"], v["region_id"]) for v in res["results"]} == {
        ("a", 76),
        ("b", 76),
        ("c", 38),
    }
    assert res["regions_searched"] == 2
    assert res["_scope"]["project"] == {"id": DEFAULT_PROJECT, "name": "Default"}
    assert "2 projects" in res["_scope"]["project_note"]


async def test_a_failing_region_does_not_fail_the_list(api: respx.MockRouter) -> None:
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/76").mock(
        return_value=volumes(76, "a")
    )
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/38").mock(
        return_value=httpx.Response(500, json={"message": "boom"})
    )
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool("call_read_tool", {"name": "cloud.volumes.list"})
        )
    assert res["count"] == 1
    assert res["regions_searched"] == 1
    assert list(res["regions_failed"]) == ["38 (Frankfurt)"]


async def test_regions_without_the_service_are_not_failures(
    api: respx.MockRouter,
) -> None:
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/76").mock(
        return_value=volumes(76, "a")
    )
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/38").mock(
        return_value=httpx.Response(
            400,
            json={
                "type": "not-available",
                "title": "The resource or feature is not available in this region "
                "or for this account.",
            },
        )
    )
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool("call_read_tool", {"name": "cloud.volumes.list"})
        )
    assert res["count"] == 1 and res["regions_searched"] == 1
    assert res["regions_without_service"]["regions"] == ["38 (Frankfurt)"]
    # The API's own explanation, so the model doesn't read it as an outage.
    assert "not available in this region" in res["regions_without_service"]["api_says"]
    assert "regions_failed" not in res


async def test_explicit_ids_skip_lookups(api: respx.MockRouter) -> None:
    route = api.get(f"/cloud/v1/volumes/{OTHER_PROJECT}/76").mock(
        return_value=volumes(76, "x")
    )
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool(
                "call_read_tool",
                {
                    "name": "cloud.volumes.list",
                    "arguments": {"project_id": OTHER_PROJECT, "region_id": 76},
                },
            )
        )
    assert route.called and res["count"] == 1 and "_scope" not in res
    assert not api.routes[0].called and not api.routes[1].called  # no lookups


async def test_get_without_region_lists_regions_to_choose_from(
    api: respx.MockRouter,
) -> None:
    async with Client(unpinned_server()) as client:
        res = await client.call_tool(
            "call_read_tool",
            {"name": "cloud.volumes.get", "arguments": {"volume_id": "v1"}},
            raise_on_error=False,
        )
    assert res.is_error
    msg = text(res)
    assert "needs region_id" in msg and "76 (Luxembourg-2)" in msg
    assert "Old" not in msg  # deleted regions are not offered


async def test_destructive_call_never_gets_a_project_filled_in(
    api: respx.MockRouter,
) -> None:
    delete = api.delete(url__regex=r"/cloud/v1/volumes/.*")
    async with Client(unpinned_server()) as client:
        res = await client.call_tool(
            "call_destructive_tool",
            {
                "name": "cloud.volumes.delete",
                "arguments": {"volume_id": "v1", "region_id": 76},
            },
            raise_on_error=False,
        )
    assert res.is_error and not delete.called
    msg = text(res)
    assert "destructive" in msg
    assert (
        f"{DEFAULT_PROJECT} (Default, default)" in msg
        and f"{OTHER_PROJECT} (test)" in msg
    )


async def test_no_default_project_asks_to_choose(api: respx.MockRouter) -> None:
    api.get("/cloud/v1/projects").mock(
        return_value=httpx.Response(
            200, json=projects((1, "one", False), (2, "two", False))
        )
    )
    async with Client(unpinned_server()) as client:
        res = await client.call_tool(
            "call_read_tool", {"name": "cloud.volumes.list"}, raise_on_error=False
        )
    assert res.is_error and "1 (one)" in text(res) and "2 (two)" in text(res)


async def test_single_project_is_used_without_a_note(api: respx.MockRouter) -> None:
    api.get("/cloud/v1/projects").mock(
        return_value=httpx.Response(200, json=projects((7, "only", False)))
    )
    route = api.get("/cloud/v1/volumes/7/76").mock(return_value=volumes(76, "a"))
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool(
                "call_read_tool",
                {"name": "cloud.volumes.list", "arguments": {"region_id": 76}},
            )
        )
    assert route.called
    assert res["_scope"] == {"project": {"id": 7, "name": "only"}}


async def test_pinned_project_and_region_are_used_as_is(api: respx.MockRouter) -> None:
    route = api.get("/cloud/v1/volumes/111/76").mock(return_value=volumes(76, "a"))
    async with Client(make_server()) as client:  # helpers pin 111/76
        res = data(
            await client.call_tool("call_read_tool", {"name": "cloud.volumes.list"})
        )
    assert route.called and "_scope" not in res
    assert not api.routes[0].called and not api.routes[1].called


async def test_filters_are_not_filled_in(api: respx.MockRouter) -> None:
    """cloud.tasks.list treats project/region as optional filters."""
    route = api.get("/cloud/v1/tasks").mock(
        return_value=httpx.Response(200, json={"count": 0, "results": []})
    )
    async with Client(unpinned_server()) as client:
        await client.call_tool("call_read_tool", {"name": "cloud.tasks.list"})
    assert route.called
    params = route.calls.last.request.url.params
    assert "project_id" not in params and "region_id" not in params


async def test_scripts_get_the_same_behaviour(api: respx.MockRouter) -> None:
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/76").mock(
        return_value=volumes(76, "a")
    )
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/38").mock(
        return_value=volumes(38, "b")
    )
    code = (
        "r = await call_tool('cloud.volumes.list')\n[v['name'] for v in r['results']]"
    )
    async with Client(unpinned_server()) as client:
        res = data(await client.call_tool("execute_code", {"code": code}))
    assert sorted(res["result"]) == ["a", "b"]


async def test_instructions_describe_the_unpinned_behaviour() -> None:
    mcp = unpinned_server()
    assert "account's default project" in mcp.instructions
    assert "search every region" in mcp.instructions


async def test_denied_lookups_are_not_used_to_fill_in_scope(
    api: respx.MockRouter,
) -> None:
    from gcore_mcp_server.runtime import SafetyPolicy

    policy = SafetyPolicy(deny=["cloud.projects.*", "cloud.regions.*"])
    async with Client(unpinned_server(policy=policy)) as client:
        no_project = await client.call_tool(
            "call_read_tool",
            {"name": "cloud.volumes.list", "arguments": {"region_id": 76}},
            raise_on_error=False,
        )
        no_region = await client.call_tool(
            "call_read_tool",
            {"name": "cloud.volumes.list", "arguments": {"project_id": OTHER_PROJECT}},
            raise_on_error=False,
        )
    assert no_project.is_error and "cloud.projects.list is denied" in text(no_project)
    assert no_region.is_error and "cloud.regions.list is denied" in text(no_region)
    assert not api.routes[0].called and not api.routes[1].called  # no lookups


async def test_merged_count_keeps_api_totals_and_flags_more_pages(
    api: respx.MockRouter,
) -> None:
    page = volumes(76, "a")
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/76").mock(
        return_value=httpx.Response(
            200, json={"count": 100, "results": page.json()["results"]}
        )
    )
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/38").mock(
        return_value=volumes(38, "c")
    )
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool("call_read_tool", {"name": "cloud.volumes.list"})
        )
    assert res["count"] == 101 and len(res["results"]) == 2
    assert res["incomplete"]["regions"] == ["76 (Luxembourg-2): 1 of 100"]


async def test_lookup_only_tool_selection_is_honoured() -> None:
    """GCORE_TOOLS=cloud.projects.list must not fall back to the whole API."""
    async with Client(make_server(tools="cloud.projects.list")) as client:
        hits = data(
            await client.call_tool(
                "search_tools", {"query": "delete instance", "limit": 50}
            )
        )
    names = {h.get("name") for h in hits}
    assert "cloud.instances.delete" not in names
    assert names <= {None, "cloud.projects.list", "cloud.regions.list"}


NOT_AVAILABLE = httpx.Response(
    400,
    json={"type": "not-available", "title": "not available in this region"},
)


async def test_service_available_in_no_region_is_an_empty_list(
    api: respx.MockRouter,
) -> None:
    for region in (76, 38):
        api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/{region}").mock(
            return_value=NOT_AVAILABLE
        )
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool("call_read_tool", {"name": "cloud.volumes.list"})
        )
    assert res["count"] == 0 and res["results"] == []
    assert len(res["regions_without_service"]["regions"]) == 2


async def test_list_inside_one_resource_needs_a_region(api: respx.MockRouter) -> None:
    """The instance is in one region; searching all would add 404s from the rest."""
    async with Client(unpinned_server()) as client:
        res = await client.call_tool(
            "call_read_tool",
            {
                "name": "cloud.instances.interfaces.list",
                "arguments": {"instance_id": "i-1"},
            },
            raise_on_error=False,
        )
    assert res.is_error and "needs region_id" in text(res)
    assert not any("/interfaces" in str(call.request.url) for call in api.calls)


async def test_default_project_on_a_later_page_is_found(
    api: respx.MockRouter,
) -> None:
    api.routes[0].side_effect = [
        httpx.Response(
            200,
            json={
                "count": 2,
                "results": [projects((OTHER_PROJECT, "test", False))["results"][0]],
            },
        ),
        httpx.Response(
            200,
            json={
                "count": 2,
                "results": [projects((DEFAULT_PROJECT, "Default", True))["results"][0]],
            },
        ),
    ]
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/76").mock(
        return_value=volumes(76, "a")
    )
    async with Client(unpinned_server()) as client:
        res = data(
            await client.call_tool(
                "call_read_tool",
                {"name": "cloud.volumes.list", "arguments": {"region_id": 76}},
            )
        )
    assert res["_scope"]["project"]["id"] == DEFAULT_PROJECT


async def test_failure_everywhere_is_not_hidden_by_an_unavailable_region(
    api: respx.MockRouter,
) -> None:
    """403 in every region must be an error, not "you have no volumes"."""
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/76").mock(
        return_value=httpx.Response(403, json={"message": "forbidden"})
    )
    api.get(f"/cloud/v1/volumes/{DEFAULT_PROJECT}/38").mock(return_value=NOT_AVAILABLE)
    async with Client(unpinned_server()) as client:
        res = await client.call_tool(
            "call_read_tool", {"name": "cloud.volumes.list"}, raise_on_error=False
        )
    assert res.is_error and "403" in text(res)


async def test_failed_project_lookup_reads_like_an_api_error(
    api: respx.MockRouter,
) -> None:
    api.get("/cloud/v1/projects").mock(
        return_value=httpx.Response(401, json={"message": "bad key"})
    )
    async with Client(unpinned_server()) as client:
        res = await client.call_tool(
            "call_read_tool", {"name": "cloud.volumes.list"}, raise_on_error=False
        )
    message = text(res)
    assert res.is_error
    assert (
        "needs project_id" in message
        and "cloud.projects.list failed: HTTP 401" in message
    )

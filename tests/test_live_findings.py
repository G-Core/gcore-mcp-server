"""Regressions for issues found in live runs with Claude Code, Codex and opencode."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client

from gcore_mcp_server.config.server_config import Mode
from gcore_mcp_server.runtime import ConfirmMode, SafetyPolicy

from tests.helpers import BASE_URL, data, full_catalog, make_client, make_server, text

pytestmark = pytest.mark.anyio

CLIENT_ID = 3621


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.get("/cloud/v1/projects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 1,
                    "results": [
                        {
                            "id": 6,
                            "name": "Default",
                            "is_default": True,
                            "state": "ACTIVE",
                            "client_id": CLIENT_ID,
                        }
                    ],
                },
            )
        )
        mock.get(re.compile(r"/cloud/v1/ssh_keys/\d+$")).mock(
            return_value=httpx.Response(
                200, json={"count": 1, "results": [{"id": "k1", "name": "a" * 30}]}
            )
        )
        yield mock


# ------------------------------------------------ results: text, no copy


async def test_results_are_text_only_in_dynamic_mode(api: respx.MockRouter) -> None:
    """A structuredContent copy would be read twice by clients like Codex."""
    calls: list[tuple[str, dict[str, Any]]] = [
        ("search_tools", {"query": "dns zones"}),
        ("get_tool_schema", {"name": "cloud.ssh_keys.list"}),
        ("call_read_tool", {"name": "cloud.ssh_keys.list"}),
        ("execute_code", {"code": "1 + 1"}),
    ]
    async with Client(make_server()) as client:
        for name, args in calls:
            res = await client.call_tool(name, args)
            assert res.structured_content is None, name
            json.loads(text(res))  # one JSON text block


async def test_results_are_text_only_in_direct_mode(api: respx.MockRouter) -> None:
    async with Client(make_server(Mode.DIRECT, tools="cloud.ssh_keys.*")) as client:
        res = await client.call_tool("cloud_ssh_keys_list", {})
    assert res.structured_content is None
    assert data(res)["results"][0]["id"] == "k1"


async def test_direct_mode_never_suggests_execute_code(api: respx.MockRouter) -> None:
    server = make_server(Mode.DIRECT, tools="cloud.ssh_keys.*", max_result_chars=60)
    async with Client(server) as client:
        res = data(await client.call_tool("cloud_ssh_keys_list", {}))
    hint = json.dumps(res)
    assert "Result too large" in hint and "execute_code" not in hint


# --------------------------------------------------------- error hints


def _status_error(status: int, body: dict[str, Any]) -> Exception:
    import gcore

    request = httpx.Request("DELETE", f"{BASE_URL}/x")
    response = httpx.Response(status, json=body, request=request)
    return gcore.APIStatusError("error", response=response, body=body)


def test_the_apis_own_hint_wins() -> None:
    from gcore_mcp_server.runtime.shaping import describe_error

    message = describe_error(
        _status_error(
            400,
            {
                "type": "resource-in-use",
                "hint": "Delete or detach the resources in 'blocking_resources'.",
            },
        ),
        "cloud.volumes.delete",
    )
    assert "Hint: Delete or detach the resources" in message
    assert "get_tool_schema" not in message
    assert message.count("Delete or detach") == 1  # not also inside the JSON


def test_not_found_mentions_project_and_region_only_for_cloud() -> None:
    from gcore_mcp_server.runtime.shaping import describe_error

    dns = describe_error(
        _status_error(404, {"error": "zone is not found"}), "dns.zones.get"
    )
    cloud = describe_error(_status_error(404, {}), "cloud.volumes.get")
    assert "project_id" not in dns and "project_id" in cloud


# --------------------------------------------------------------- search


def test_listing_a_resource_shows_its_own_operations_first() -> None:
    names = [h.get("name") for h in full_catalog().search("cloud.volumes")]
    assert "cloud.volumes.list" in names  # was cut off alphabetically


def test_listing_a_service_shows_its_resources() -> None:
    hits = full_catalog().search("cloud")
    assert {"resource": "cloud.volumes", "operations": 16} in hits
    assert all("resource" in h for h in hits)


def test_long_resource_listings_say_what_is_hidden() -> None:
    hits = full_catalog().search("cloud.load_balancers")
    assert "more" in hits[-1]
    assert "cloud.load_balancers.pools" in hits[-1]["sub_resources"]


def test_ranked_search_still_defaults_to_ten() -> None:
    assert len(full_catalog().search("list volumes")) <= 10


# ------------------------------------------------------------- client_id


async def test_client_id_is_filled_in_like_the_default_project(
    api: respx.MockRouter,
) -> None:
    quotas = api.get(f"/cloud/v2/global_quotas/{CLIENT_ID}").mock(
        return_value=httpx.Response(200, json={"keypair_count_limit": 100})
    )
    server = make_server(client=make_client(project=None, region=None))
    async with Client(server) as client:
        res = data(
            await client.call_tool(
                "call_read_tool", {"name": "cloud.quotas.get_global"}
            )
        )
    assert quotas.called
    assert res["_scope"]["client_id"] == CLIENT_ID


async def test_destructive_calls_need_client_id_explicitly(
    api: respx.MockRouter,
) -> None:
    server = make_server(
        client=make_client(project=None, region=None),
        policy=SafetyPolicy(confirm=ConfirmMode.NONE),
    )
    async with Client(server) as client:
        res = await client.call_tool(
            "call_destructive_tool",
            {"name": "iam.api_tokens.delete", "arguments": {"token_id": 1}},
            raise_on_error=False,
        )
    assert res.is_error and "needs client_id" in text(res)
    assert str(CLIENT_ID) in text(res)  # the value to use is right there


def test_client_id_is_optional_in_schemas() -> None:
    catalog = full_catalog()
    filled = [e.name for e in catalog.entries if e.fills_client_id]
    assert "cloud.quotas.get_by_region" in filled and "iam.api_tokens.list" in filled
    for name in filled:
        assert "client_id" not in catalog.resolve(name).required_params, name


# ------------------------------------------------------------ summaries


def test_undocumented_methods_get_real_summaries() -> None:
    catalog = full_catalog()
    for entry in catalog.entries:
        verb = entry.name.rsplit(".", 1)[-1].replace("_", " ")
        assert not entry.summary.startswith(f"{verb} {entry.group}"), entry.name
    # From the overload's docstring, and from the documented *_and_poll twin.
    assert catalog.resolve("cdn.origin_groups.create").summary.startswith(
        "Create an origin group"
    )
    assert "poll" not in catalog.resolve("cloud.instances.action").summary.lower()


# ------------------------------------------------------- explicit nulls


async def test_an_explicit_null_reaches_the_api(api: respx.MockRouter) -> None:
    """Seen live: port_id: null (unassign) was dropped, so nothing changed."""
    patch = api.patch(re.compile(r"/cloud/v\d/floatingips/\d+/\d+/fip1$")).mock(
        return_value=httpx.Response(200, json={"id": "fip1", "status": "DOWN"})
    )
    server = make_server(policy=SafetyPolicy(confirm=ConfirmMode.NONE))
    async with Client(server) as client:
        await client.call_tool(
            "call_destructive_tool",
            {
                "name": "cloud.floating_ips.update",
                "arguments": {"floating_ip_id": "fip1", "port_id": None},
            },
        )
    body = json.loads(patch.calls.last.request.content)
    assert body == {"port_id": None}


async def test_omitted_arguments_are_still_not_sent(api: respx.MockRouter) -> None:
    patch = api.patch(re.compile(r"/cloud/v\d/floatingips/\d+/\d+/fip1$")).mock(
        return_value=httpx.Response(200, json={"id": "fip1", "status": "ACTIVE"})
    )
    server = make_server(policy=SafetyPolicy(confirm=ConfirmMode.NONE))
    async with Client(server) as client:
        await client.call_tool(
            "call_destructive_tool",
            {
                "name": "cloud.floating_ips.update",
                "arguments": {"floating_ip_id": "fip1", "port_id": "p1"},
            },
        )
    assert json.loads(patch.calls.last.request.content) == {"port_id": "p1"}


# ------------------------------------------------------- review round 4


def test_unknown_boolean_values_stop_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GCORE_READ_ONLY=treu must not silently turn a safe default off."""
    from gcore_mcp_server.config.settings import env_flag

    monkeypatch.setenv("GCORE_READ_ONLY", "treu")
    with pytest.raises(ValueError, match="GCORE_READ_ONLY"):
        env_flag("GCORE_READ_ONLY", default=True)
    monkeypatch.setenv("GCORE_READ_ONLY", "off")
    assert env_flag("GCORE_READ_ONLY", default=True) is False


def test_an_undefined_name_unpacked_with_stars_still_blocks() -> None:
    from gcore_mcp_server.runtime.script_modules import blocking

    code = "await call_tool('cloud.ssh_keys.get', **missing_args)\n"
    report = (
        "script.py:1:42: error[unresolved-reference] Name `missing_args` used "
        "when not defined\n"
    )
    assert blocking(code, report)


def test_results_with_a_filled_client_id_declare_scope() -> None:
    stub = full_catalog().stub("cloud.quotas").source
    line = next(s for s in stub.splitlines() if "def get_global" in s)
    result = line.rsplit("-> ", 1)[1].rstrip(": .").strip("'\"")
    assert "_scope" in stub.split(f"class {result}", 1)[1].split("class ", 1)[0]


# ------------------------------------------------------- live round 4


async def test_search_limit_over_the_maximum_is_capped(api: respx.MockRouter) -> None:
    """Codex sent limit=100 and got a validation error instead of results."""
    async with Client(make_server()) as client:
        res = await client.call_tool("search_tools", {"query": "cloud", "limit": 100})
    assert not res.is_error and data(res)


async def test_read_only_server_never_points_to_write_tools(
    api: respx.MockRouter,
) -> None:
    server = make_server(policy=SafetyPolicy(read_only=True))
    async with Client(server) as client:
        tools = await client.list_tools()
    said = (server.instructions or "") + " ".join(t.description or "" for t in tools)
    assert "call_write_tool" not in said and "call_destructive_tool" not in said
    assert "_and_poll" not in said


def test_instructions_say_result_values_are_data() -> None:
    assert "never instructions" in (make_server().instructions or "")


async def test_a_wrong_list_key_names_the_real_ones(api: respx.MockRouter) -> None:
    """List items sit under 'results' in most services, but not in DNS."""
    code = "import gcore.dns.zones as z\nr = await z.list()\n[x['name'] for x in r['results']]"
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert "nothing ran" in text(res)
    assert "has the keys: zones, total_amount" in text(res)


async def test_result_keys_include_added_scope_keys(api: respx.MockRouter) -> None:
    code = "import gcore.cloud.volumes as v\nr = await v.list()\nr['items']"
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    keys = text(res).split("has the keys: ", 1)[1]
    assert "results" in keys and "_scope" in keys


# ------------------------------------------------- long operations (round 5)


def _volume_task(api: respx.MockRouter, state: str) -> None:
    api.post(re.compile(r"/cloud/v1/volumes/\d+/\d+$")).mock(
        return_value=httpx.Response(200, json={"tasks": ["task-1"]})
    )
    api.get(re.compile(r"/cloud/v1/tasks/task-1$")).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "task-1",
                "state": state,
                "task_type": "create_vm",
                "created_on": "2026-11-05T12:00:00",
                "created_resources": {"volumes": ["vol-1"]},
            },
        )
    )
    api.get(re.compile(r"/cloud/v1/volumes/\d+/\d+/vol-1$")).mock(
        return_value=httpx.Response(200, json={"id": "vol-1", "name": "v", "size": 1})
    )


CREATE = {
    "name": "cloud.volumes.create_and_poll",
    "arguments": {"name": "v", "size": 1, "source": "new-volume", "region_id": 76},
}


async def test_a_task_that_outlasts_the_wait_returns_its_id(
    api: respx.MockRouter,
) -> None:
    """Seen live: opencode gave up at 60 s on a 90 s load balancer create."""
    _volume_task(api, "RUNNING")
    async with Client(make_server(wait_secs=0.3)) as client:
        res = await client.call_tool("call_write_tool", CREATE)
    out = data(res)
    assert not res.is_error and out["still_running"] is True
    assert out["tasks"] == ["task-1"]
    assert "cloud.tasks.poll(task_id='task-1')" in out["hint"]
    assert "Do not call cloud.volumes.create_and_poll again" in out["hint"]
    assert "cloud.volumes.get" in out["hint"]


async def test_a_task_within_the_wait_returns_the_resource(
    api: respx.MockRouter,
) -> None:
    _volume_task(api, "FINISHED")
    async with Client(make_server(wait_secs=30)) as client:
        out = data(await client.call_tool("call_write_tool", CREATE))
    assert out["id"] == "vol-1" and "still_running" not in out


def test_instructions_explain_still_running() -> None:
    said = make_server().instructions or ""
    assert "still_running" in said and "cloud.tasks.poll" in said
    assert "still_running" not in (make_server(wait_secs=None).instructions or "")


def test_wait_timeout_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    from gcore_mcp_server.config.server_config import ServerConfig

    assert ServerConfig.from_env().wait_secs == 50
    monkeypatch.setenv("GCORE_WAIT_TIMEOUT", "0")
    assert ServerConfig.from_env().wait_secs is None
    monkeypatch.setenv("GCORE_WAIT_TIMEOUT", "-3")
    config = ServerConfig.from_env()
    assert config.wait_secs == 50 and any(
        "GCORE_WAIT_TIMEOUT" in n for n in config.notes
    )


async def test_progress_is_reported_while_waiting(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gcore_mcp_server.runtime import waiting

    monkeypatch.setattr(waiting, "PROGRESS_EVERY_SECS", 0.1)
    _volume_task(api, "RUNNING")
    seen: list[str] = []

    async def on_progress(
        progress: float, total: float | None, message: str | None
    ) -> None:
        seen.append(message or "")

    async with Client(
        make_server(wait_secs=0.5), progress_handler=on_progress
    ) as client:
        await client.call_tool("call_write_tool", CREATE)
    assert seen and "waiting for the task" in seen[0]


async def test_waiting_again_on_a_task_is_bounded_too(api: respx.MockRouter) -> None:
    """cloud.tasks.poll waits as well; unbounded it would time the client out."""
    _volume_task(api, "RUNNING")
    async with Client(make_server(wait_secs=0.3)) as client:
        out = data(
            await client.call_tool(
                "call_read_tool",
                {"name": "cloud.tasks.poll", "arguments": {"task_id": "task-1"}},
            )
        )
    assert out["still_running"] is True and out["tasks"] == ["task-1"]
    # Seen live: "Don't run it again: wait with cloud.tasks.poll" read as a
    # contradiction when the call was cloud.tasks.poll itself.
    assert "Do not call" not in out["hint"]
    assert "call cloud.tasks.poll(task_id='task-1') again" in out["hint"]


def test_polling_knobs_are_not_offered() -> None:
    entry = full_catalog().resolve("cloud.load_balancers.create_and_poll")
    assert entry is not None
    assert "polling_timeout_seconds" not in entry.param_names


def test_task_results_list_only_the_resources_created() -> None:
    """Seen live: ~40 empty created_resources arrays in every task result."""
    from gcore.types.cloud import Task

    from gcore_mcp_server.runtime.shaping import to_jsonable

    task = Task.model_validate(
        {
            "id": "t",
            "state": "FINISHED",
            "task_type": "create_loadbalancer",
            "created_on": "2026-11-05T12:00:00",
            "user_id": 1,
            "created_resources": {
                "loadbalancers": ["lb-1"],
                "volumes": [],
                "ports": [],
            },
        }
    )
    out = to_jsonable(task)
    assert out["created_resources"] == {"loadbalancers": ["lb-1"]}


# ---------------------------------------------------------- live round 6


async def test_a_script_stopped_by_its_limit_lists_the_tasks_it_started(
    api: respx.MockRouter,
) -> None:
    """Seen live: all three harnesses lost track of a ~90 s create in a script."""
    _volume_task(api, "RUNNING")
    code = (
        "import gcore.cloud.volumes as volumes\n"
        "await volumes.create_and_poll(name='v', size=1, source='new-volume', "
        "region_id=76)"
    )
    server = make_server(code_writes=True, code_timeout_secs=2)
    async with Client(server) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    said = text(res)
    assert "exceeded 2 s" in said and "'task-1'" in said
    assert "Do NOT rerun the script" in said and "cloud.tasks.poll" in said


def test_schemas_and_instructions_say_missing_means_null() -> None:
    """Seen live: rules without remote_ip_prefix (any source) read as closed."""
    schema = full_catalog().describe(
        full_catalog().resolve("cloud.security_groups.list")
    )  # type: ignore[arg-type]
    assert "missing key means the value is null" in schema["returns"]["note"]
    assert "remote_ip_prefix" in (make_server().instructions or "")


def test_list_accepts_comma_separated_patterns() -> None:
    """The server's own hint suggests --list '<GCORE_TOOLS value>'."""
    from gcore_mcp_server.catalog.export import list_operations

    lines = list_operations(
        full_catalog(),
        ["cloud.k8s.clusters.kubeconfig.*,cloud.k8s.clusters.get_certificate"],
    )
    assert lines[-1].startswith("2 of ")


async def test_a_script_waiting_on_a_task_names_it_if_stopped(
    api: respx.MockRouter,
) -> None:
    _volume_task(api, "RUNNING")
    code = "import gcore.cloud.tasks as tasks\nawait tasks.poll(task_id='task-1')"
    async with Client(make_server(code_timeout_secs=2)) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert "'task-1'" in text(res)


# ------------------------------------------------------ batch approval


def _volume_deletes(api: respx.MockRouter) -> respx.Route:
    return api.delete(re.compile(r"/cloud/v1/volumes/\d+/\d+/vol-\d$")).mock(
        side_effect=lambda request: httpx.Response(
            404 if request.url.path.endswith("vol-9") else 200,
            json={"tasks": []}
            if not request.url.path.endswith("vol-9")
            else {"detail": "gone"},
        )
    )


BATCH = {
    "name": "cloud.volumes.delete",
    "arguments": [
        {"volume_id": "vol-1", "project_id": 6, "region_id": 76},
        {"volume_id": "vol-2", "project_id": 6, "region_id": 76},
        {"volume_id": "vol-9", "project_id": 6, "region_id": 76},
    ],
}


async def test_a_batch_is_approved_once_listing_every_item(
    api: respx.MockRouter,
) -> None:
    """Seen live: four deletes took eight calls (refused, then with a token)."""
    deletes = _volume_deletes(api)
    async with Client(make_server()) as client:
        ask = await client.call_tool(
            "call_destructive_tool", BATCH, raise_on_error=False
        )
        prompt = text(ask)
        assert "CONFIRMATION REQUIRED" in prompt and not deletes.called
        assert all(v in prompt for v in ("vol-1", "vol-2", "vol-9"))
        assert "3 items in project 6, region 76" in prompt
        token = re.search(r'confirm_token="(\w+)"', prompt)[1]  # type: ignore[index]
        out = data(
            await client.call_tool(
                "call_destructive_tool", {**BATCH, "confirm_token": token}
            )
        )
    assert deletes.call_count == 3
    assert out["succeeded"] == 2 and out["failed"] == 1
    assert "error" in out["results"][2] and "result" in out["results"][0]


async def test_a_batch_token_does_not_approve_a_different_list(
    api: respx.MockRouter,
) -> None:
    deletes = _volume_deletes(api)
    async with Client(make_server()) as client:
        ask = await client.call_tool(
            "call_destructive_tool", BATCH, raise_on_error=False
        )
        token = re.search(r'confirm_token="(\w+)"', text(ask))[1]  # type: ignore[index]
        longer = {
            **BATCH,
            "arguments": [
                *BATCH["arguments"],
                {"volume_id": "vol-3", "project_id": 6, "region_id": 76},
            ],
            "confirm_token": token,
        }
        res = await client.call_tool(
            "call_destructive_tool", longer, raise_on_error=False
        )
    assert "CONFIRMATION REQUIRED" in text(res) and not deletes.called


async def test_batches_are_capped(api: respx.MockRouter) -> None:
    many = {
        "name": "cloud.volumes.delete",
        "arguments": [
            {"volume_id": f"v{i}", "project_id": 6, "region_id": 76} for i in range(21)
        ],
    }
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_destructive_tool", many, raise_on_error=False
        )
    assert res.is_error and "at most 20" in text(res)


# ------------------------------------------------ readable approval prompts


async def test_approval_prompts_name_the_targets(api: respx.MockRouter) -> None:
    """Seen live: a 12-item prompt showed only UUIDs, folded after line 2."""
    api.get(re.compile(r"/cloud/v1/floatingips/\d+/\d+/fip-(\d)$")).mock(
        side_effect=lambda request: httpx.Response(
            200,
            json={
                "id": request.url.path.rsplit("/", 1)[1],
                "floating_ip_address": f"45.82.30.{request.url.path[-1]}",
                "status": "DOWN",
            },
        )
    )
    batch = {
        "name": "cloud.floating_ips.delete",
        "arguments": [
            {"floating_ip_id": f"fip-{i}", "project_id": 6, "region_id": 76}
            for i in (1, 2)
        ],
    }
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_destructive_tool", batch, raise_on_error=False
        )
    lines = text(res).splitlines()
    # The first lines carry the decision: what, where, and which by name.
    assert "DESTRUCTIVE" in lines[0]
    assert lines[1] == "2 items in project 6, region 76: 45.82.30.1, 45.82.30.2"
    assert "45.82.30.1 - floating_ip_id fip-1" in lines[2]
    assert "project_id" not in lines[2]  # said once, above


def test_accept_means_approve_unless_the_box_is_unticked() -> None:
    """Seen live: Enter on Accept went back to a required, unticked box."""
    from gcore_mcp_server.runtime.safety import _answer  # pyright: ignore[reportPrivateUsage]

    assert _answer("accept", None) == "approved"
    assert _answer("accept", True) == "approved"
    assert _answer("accept", False) == "declined"
    assert _answer("decline", None) == "declined"
    assert _answer("cancel", None) == "unanswered"

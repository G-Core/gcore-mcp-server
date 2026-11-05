"""Safety controls must hold on every path: direct tools, call_tool, execute_code."""

from __future__ import annotations

import re
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client

from gcore_mcp_server.config.server_config import Mode
from gcore_mcp_server.runtime import ConfirmMode, SafetyPolicy, policy_from_env

from tests.helpers import BASE_URL, PROJECT_ID, data, make_server, text

pytestmark = pytest.mark.anyio

DELETE_ARGS = {"name": "cloud.ssh_keys.delete", "arguments": {"ssh_key_id": "k1"}}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api():
    """Mock API that records every request; nothing reaches the network."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.delete(re.compile(r"/cloud/v1/ssh_keys/.*")).mock(
            return_value=httpx.Response(204)
        )
        mock.post(re.compile(r"/cloud/v1/ssh_keys/.*")).mock(
            return_value=httpx.Response(200, json={"id": "k2", "name": "n"})
        )
        mock.get(re.compile(r"/cloud/v1/ssh_keys/.*")).mock(
            return_value=httpx.Response(200, json={"count": 0, "results": []})
        )
        yield mock


def mutating_calls(api: respx.MockRouter) -> list[str]:
    return [c.request.method for c in api.calls if c.request.method != "GET"]


def token_from(message: str) -> str:
    match = re.search(r'confirm_token="([0-9a-f]+)"', message)
    assert match, message
    return match.group(1)


# ---------------------------------------------------------------- read-only


async def test_read_only_blocks_writes_via_call_tool(api: respx.MockRouter) -> None:
    server = make_server(policy=SafetyPolicy(read_only=True))
    async with Client(server) as client:
        # Only the read tool exists; trying a write through it explains why.
        res = await client.call_tool(
            "call_read_tool",
            {"name": "cloud.ssh_keys.create", "arguments": {"name": "x"}},
            raise_on_error=False,
        )
        ok = await client.call_tool("call_read_tool", {"name": "cloud.ssh_keys.list"})
    assert res.is_error and "read-only" in text(res)
    assert not ok.is_error
    assert mutating_calls(api) == []


async def test_read_only_blocks_writes_inside_code(api: respx.MockRouter) -> None:
    code = (
        "await call_tool('cloud.ssh_keys.delete', ssh_key_id='k1', confirm_token='x')"
    )
    server = make_server(policy=SafetyPolicy(read_only=True))
    async with Client(server) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error and "read-only" in text(res)
    assert mutating_calls(api) == []


async def test_read_only_direct_mode_does_not_advertise_writes() -> None:
    server = make_server(
        Mode.DIRECT, tools="cloud.ssh_keys.*", policy=SafetyPolicy(read_only=True)
    )
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
    assert "cloud_ssh_keys_list" in names
    assert "cloud_ssh_keys_create" not in names and "cloud_ssh_keys_delete" not in names


async def test_read_only_offers_only_read_tools() -> None:
    async with Client(make_server(policy=SafetyPolicy(read_only=True))) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert "call_write_tool" not in tools and "call_destructive_tool" not in tools
    assert all(t.annotations.read_only_hint is True for t in tools.values())


async def test_schema_reports_blocked_and_confirmation() -> None:
    async with Client(make_server(policy=SafetyPolicy(read_only=True))) as client:
        blocked = data(
            await client.call_tool("get_tool_schema", {"name": "cloud.ssh_keys.delete"})
        )
    async with Client(make_server()) as client:
        confirm = data(
            await client.call_tool("get_tool_schema", {"name": "cloud.ssh_keys.delete"})
        )
    assert "read-only" in blocked["blocked"]
    assert confirm["requires_confirmation"] is True


# ---------------------------------------------------------------- deny-list


async def test_denied_operations_are_shown_blocked_and_uncallable(
    api: respx.MockRouter,
) -> None:
    policy = SafetyPolicy(deny=["cloud.ssh_keys.delete", "dns.*"])
    async with Client(make_server(policy=policy)) as client:
        hits = data(await client.call_tool("search_tools", {"query": "cloud.ssh_keys"}))
        dns = data(await client.call_tool("search_tools", {"query": "dns zones"}))
        res = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
        code = await client.call_tool(
            "execute_code",
            {"code": "await call_tool('cloud.ssh_keys.delete', ssh_key_id='k1')"},
            raise_on_error=False,
        )
    # Listed, so a model knows not to look for another way; never runnable.
    by_name = {h.get("name"): h for h in hits}
    assert "deny-list" in by_name["cloud.ssh_keys.delete"]["blocked"]
    assert "blocked" not in by_name["cloud.ssh_keys.list"]
    assert all("blocked" in h for h in dns if h.get("name", "").startswith("dns."))
    assert res.is_error and "deny-list" in text(res)
    assert code.is_error
    assert mutating_calls(api) == []


async def test_denied_direct_tools_are_not_registered() -> None:
    policy = SafetyPolicy(deny=["cloud.ssh_keys.delete"])
    server = make_server(Mode.DIRECT, tools="cloud.ssh_keys.*", policy=policy)
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
    assert "cloud_ssh_keys_delete" not in names and "cloud_ssh_keys_get" in names


# ---------------------------------------------------------------- confirmation


async def test_destructive_call_needs_token_bound_to_arguments(
    api: respx.MockRouter,
) -> None:
    async with Client(make_server()) as client:
        first = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
        assert first.is_error and "CONFIRMATION REQUIRED" in text(first)
        assert mutating_calls(api) == []
        token = token_from(text(first))

        # The token does not approve a different target.
        other = await client.call_tool(
            "call_destructive_tool",
            {
                "name": "cloud.ssh_keys.delete",
                "arguments": {"ssh_key_id": "OTHER"},
                "confirm_token": token,
            },
            raise_on_error=False,
        )
        assert other.is_error and mutating_calls(api) == []

        # A made-up token is refused too.
        fake = await client.call_tool(
            "call_destructive_tool",
            {**DELETE_ARGS, "confirm_token": "0123456789abcdef"},
            raise_on_error=False,
        )
        assert fake.is_error and mutating_calls(api) == []

        done = await client.call_tool(
            "call_destructive_tool", {**DELETE_ARGS, "confirm_token": token}
        )
    assert data(done) == {"ok": True}
    assert mutating_calls(api) == ["DELETE"]


async def test_writes_do_not_need_confirmation_by_default(
    api: respx.MockRouter,
) -> None:
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_write_tool",
            {"name": "cloud.ssh_keys.create", "arguments": {"name": "n"}},
        )
    assert data(res)["id"] == "k2"


async def test_confirm_writes_mode(api: respx.MockRouter) -> None:
    server = make_server(policy=SafetyPolicy(confirm=ConfirmMode.WRITES))
    async with Client(server) as client:
        res = await client.call_tool(
            "call_write_tool",
            {"name": "cloud.ssh_keys.create", "arguments": {"name": "n"}},
            raise_on_error=False,
        )
    assert res.is_error and "CONFIRMATION REQUIRED" in text(res)
    assert mutating_calls(api) == []


async def test_confirm_none_mode(api: respx.MockRouter) -> None:
    server = make_server(policy=SafetyPolicy(confirm=ConfirmMode.NONE))
    async with Client(server) as client:
        await client.call_tool("call_destructive_tool", DELETE_ARGS)
    assert mutating_calls(api) == ["DELETE"]


async def test_direct_tool_confirmation(api: respx.MockRouter) -> None:
    server = make_server(Mode.DIRECT, tools="cloud.ssh_keys.*")
    async with Client(server) as client:
        first = await client.call_tool(
            "cloud_ssh_keys_delete", {"ssh_key_id": "k1"}, raise_on_error=False
        )
        assert first.is_error and mutating_calls(api) == []
        await client.call_tool(
            "cloud_ssh_keys_delete",
            {"ssh_key_id": "k1", "confirm_token": token_from(text(first))},
        )
    assert mutating_calls(api) == ["DELETE"]


async def test_scripts_are_refused_without_a_token(api: respx.MockRouter) -> None:
    """A script can't approve its own call: the refusal carries no token."""
    code = "await call_tool('cloud.ssh_keys.delete', ssh_key_id='k1')"
    async with Client(make_server(code_writes=True)) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
        assert res.is_error and "APPROVAL NEEDED" in text(res)
        assert "confirm_token" not in text(res)
        assert "call_destructive_tool" in text(res)
        assert mutating_calls(api) == []
        # The suggested call goes through the normal confirmation.
        first = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
        await client.call_tool(
            "call_destructive_tool",
            {**DELETE_ARGS, "confirm_token": token_from(text(first))},
        )
    assert mutating_calls(api) == ["DELETE"]


async def test_script_cannot_approve_its_own_call(api: respx.MockRouter) -> None:
    """Catching the refusal and retrying with a token from it gets nowhere."""
    code = """
import re
try:
    await call_tool('cloud.ssh_keys.delete', ssh_key_id='k1')
except Exception as e:
    m = re.search(r'confirm_token="(\\w+)"', str(e))
    t = m.group(1) if m else 'none'
    await call_tool('cloud.ssh_keys.delete', ssh_key_id='k1', confirm_token=t)
"""
    async with Client(make_server(code_writes=True)) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error
    assert mutating_calls(api) == []


async def test_script_cannot_use_a_token_issued_to_the_model(
    api: respx.MockRouter,
) -> None:
    async with Client(make_server(code_writes=True)) as client:
        first = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
        token = token_from(text(first))
        code = f"await call_tool('cloud.ssh_keys.delete', ssh_key_id='k1', confirm_token='{token}')"
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error and "APPROVAL NEEDED" in text(res)
    assert mutating_calls(api) == []


async def test_confirmation_mid_script_says_not_to_rerun(
    api: respx.MockRouter,
) -> None:
    """Rerunning would repeat the writes that already ran."""
    code = (
        "await call_tool('cloud.ssh_keys.create', name='n')\n"
        "await call_tool('cloud.ssh_keys.delete', ssh_key_id='k2')"
    )
    async with Client(make_server(code_writes=True)) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error and "Do NOT rerun the script" in text(res)
    assert "call_destructive_tool" in text(res)
    assert mutating_calls(api) == ["POST"]


async def test_confirm_token_cannot_be_replayed(api: respx.MockRouter) -> None:
    async with Client(make_server()) as client:
        first = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
        args = {**DELETE_ARGS, "confirm_token": token_from(text(first))}
        await client.call_tool("call_destructive_tool", args)
        again = await client.call_tool(
            "call_destructive_tool", args, raise_on_error=False
        )
    assert again.is_error and "CONFIRMATION REQUIRED" in text(again)
    assert mutating_calls(api) == ["DELETE"]


# ---------------------------------------------------------------- elicitation


def _handler(answer: Any):
    seen: list[str] = []

    async def handler(
        message: str, response_type: Any, params: Any, context: Any
    ) -> Any:
        seen.append(message)
        return answer

    return handler, seen


async def test_elicitation_approve_runs_the_call(api: respx.MockRouter) -> None:
    from fastmcp.client.elicitation import ElicitResult

    handler, seen = _handler(ElicitResult(action="accept", content={"value": True}))
    async with Client(make_server(), elicitation_handler=handler) as client:
        res = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
    if not seen:
        pytest.skip("this FastMCP/protocol version does not deliver elicitation")
    assert "cloud.ssh_keys.delete" in seen[0]
    assert not res.is_error, text(res)
    assert mutating_calls(api) == ["DELETE"]


async def test_elicitation_decline_blocks_the_call(api: respx.MockRouter) -> None:
    from fastmcp.client.elicitation import ElicitResult

    handler, seen = _handler(ElicitResult(action="decline"))
    async with Client(make_server(), elicitation_handler=handler) as client:
        res = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
    if not seen:
        pytest.skip("this FastMCP/protocol version does not deliver elicitation")
    assert res.is_error and "declined" in text(res)
    assert mutating_calls(api) == []


# ---------------------------------------------------------------- configuration


def test_policy_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCORE_READ_ONLY", "true")
    monkeypatch.setenv("GCORE_CONFIRM", "writes")
    monkeypatch.setenv("GCORE_DENY_TOOLS", "cloud.projects.delete, iam.*")
    policy = policy_from_env()
    assert policy.read_only and policy.confirm is ConfirmMode.WRITES
    assert policy.is_denied("iam.users.delete") and policy.is_denied(
        "cloud.projects.delete"
    )
    assert not policy.is_denied("cloud.projects.list")

    monkeypatch.setenv("GCORE_CONFIRM", "bogus")
    assert policy_from_env().confirm is ConfirmMode.DESTRUCTIVE


def test_tokens_are_single_use_bound_to_the_call_and_per_process() -> None:
    a, b = SafetyPolicy(), SafetyPolicy()
    token = a.issue_token("x", {"a": 1})
    assert not b.consume_token("x", {"a": 1}, token)  # another process
    assert not a.consume_token("x", {"a": 2}, token)  # other arguments
    assert a.consume_token("x", {"a": 1}, token)
    assert not a.consume_token("x", {"a": 1}, token)  # replay


def test_tokens_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    import gcore_mcp_server.runtime.safety as safety

    policy = SafetyPolicy()
    token = policy.issue_token("x", {})
    now = safety.time.monotonic()
    monkeypatch.setattr(
        safety.time, "monotonic", lambda: now + safety.TOKEN_TTL_SECS + 1
    )
    assert not policy.consume_token("x", {}, token)


def test_request_state_is_not_a_confirm_token() -> None:
    """Clients may log or show request_state; it must not approve anything."""
    policy = SafetyPolicy()
    state = policy.issue_request_state("x", {"a": 1})
    assert not policy.consume_token("x", {"a": 1}, state)


class _Answer:
    action = "accept"
    content = {"value": True}


class _RetryCtx:
    """A 2026-07-28 retry carrying the user's answer and the echoed state."""

    def __init__(self, state: str):
        self.input_responses = {"gcore_confirm": _Answer()}
        self.request_state = state


def test_an_approval_works_once() -> None:
    """A recorded "yes" can't be replayed to run the call again."""
    policy = SafetyPolicy()
    state = policy.issue_request_state("x", {"a": 1})
    ctx = _RetryCtx(state)
    assert policy._guard_answer(ctx, "x", {"a": 2}, "") is None  # other call
    assert policy._guard_answer(ctx, "x", {"a": 1}, "") == "approved"
    assert policy._guard_answer(ctx, "x", {"a": 1}, "") is None  # replay
    assert policy._guard_answer(_RetryCtx("forged"), "x", {"a": 1}, "") is None


@pytest.mark.parametrize(
    ("action", "value", "expected"),
    [
        ("accept", True, "approved"),
        ("accept", False, "declined"),
        ("decline", None, "declined"),
        ("cancel", None, "unanswered"),  # headless clients cancel every prompt
    ],
)
def test_prompt_answers(action: str, value: Any, expected: str) -> None:
    from gcore_mcp_server.runtime.safety import _answer

    assert _answer(action, value) == expected


async def test_unanswered_prompt_is_not_reported_as_a_decline(
    api: respx.MockRouter,
) -> None:
    from fastmcp.client.elicitation import ElicitResult

    handler, seen = _handler(ElicitResult(action="cancel"))
    async with Client(make_server(), elicitation_handler=handler) as client:
        res = await client.call_tool(
            "call_destructive_tool", DELETE_ARGS, raise_on_error=False
        )
    if not seen:
        pytest.skip("this FastMCP/protocol version does not deliver elicitation")
    message = text(res)
    assert res.is_error and "declined" not in message
    assert "GCORE_CONFIRM_VIA=model" in message
    assert mutating_calls(api) == []


def test_tokens_are_bound_to_the_session() -> None:
    policy = SafetyPolicy()
    token = policy.issue_token("x", {"a": 1}, caller="session-a")
    assert not policy.consume_token("x", {"a": 1}, token, caller="session-b")
    assert policy.consume_token("x", {"a": 1}, token, caller="session-a")


def test_project_id_constant_is_used() -> None:
    assert PROJECT_ID == 111


def test_denying_an_operation_also_denies_its_poll_variant() -> None:
    policy = SafetyPolicy(deny=["cloud.volumes.delete"])
    assert policy.is_denied("cloud.volumes.delete")
    assert policy.is_denied("cloud.volumes.delete_and_poll")
    assert not policy.is_denied("cloud.volumes.list")


def test_deny_patterns_that_match_nothing_are_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING"):
        make_server(
            policy=SafetyPolicy(deny=["cloud.instance.delete", "cloud.volumes.*"])
        )
    warnings = [
        r.getMessage() for r in caplog.records if "GCORE_DENY_TOOLS" in r.getMessage()
    ]
    assert len(warnings) == 1 and "'cloud.instance.delete'" in warnings[0]


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, True),
        ({"GCORE_CONFIRM_VIA": "model"}, False),
        ({"GCORE_CONFIRM_VIA": "client"}, True),
        ({"GCORE_ELICITATION": "false"}, False),  # older spelling
    ],
)
def test_confirm_via_setting(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: bool
) -> None:
    for var in ("GCORE_CONFIRM_VIA", "GCORE_ELICITATION"):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert policy_from_env().use_elicitation is expected


async def test_scripts_are_read_only_by_default(api: respx.MockRouter) -> None:
    code = "await call_tool('cloud.ssh_keys.delete', ssh_key_id='k1')"
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )
    assert res.is_error and "call_destructive_tool" in text(res)
    assert "GCORE_CODE_WRITES" in text(res)
    assert mutating_calls(api) == []


async def test_call_tools_refuse_other_access_classes(api: respx.MockRouter) -> None:
    async with Client(make_server()) as client:
        res = await client.call_tool(
            "call_read_tool", DELETE_ARGS, raise_on_error=False
        )
        schema = data(
            await client.call_tool("get_tool_schema", {"name": "cloud.ssh_keys.delete"})
        )
    assert res.is_error and "call_destructive_tool" in text(res)
    assert schema["call_with"] == "call_destructive_tool"
    assert mutating_calls(api) == []

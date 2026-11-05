"""Typed gcore.* modules in execute_code: stubs, blocking rules, end to end."""

from __future__ import annotations

import re
import sys
import types
import typing
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client

from gcore_mcp_server.runtime import SafetyPolicy
from gcore_mcp_server.runtime.script_modules import (
    blocking,
    build_root,
    explain,
    imported_paths,
)

from tests.helpers import BASE_URL, data, full_catalog, make_server, text

pytestmark = pytest.mark.anyio

KEY = {"id": "k1", "name": "mine", "fingerprint": "ab:cd", "state": "ACTIVE"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.get(re.compile(r"/cloud/v1/ssh_keys/\d+$")).mock(
            return_value=httpx.Response(200, json={"count": 1, "results": [KEY]})
        )
        mock.get(re.compile(r"/cloud/v1/ssh_keys/\d+/k1$")).mock(
            return_value=httpx.Response(200, json=KEY)
        )
        mock.post(re.compile(r"/cloud/v1/ssh_keys/\d+$")).mock(
            return_value=httpx.Response(200, json={**KEY, "id": "k2"})
        )
        mock.delete(re.compile(r"/cloud/v1/ssh_keys/.*")).mock(
            return_value=httpx.Response(204)
        )
        yield mock


def api_calls(api: respx.MockRouter) -> list[str]:
    return [f"{c.request.method} {c.request.url.path}" for c in api.calls]


async def run(code: str, **server: Any) -> Any:
    async with Client(make_server(**server)) as client:
        return await client.call_tool(
            "execute_code", {"code": code}, raise_on_error=False
        )


# ------------------------------------------------------------------ stubs


def test_every_module_has_a_valid_stub() -> None:
    """Each stub is valid Python whose every annotation resolves."""
    catalog = full_catalog()
    for path in sorted(catalog.module_paths):
        module = types.ModuleType("_stub_check")
        sys.modules["_stub_check"] = module
        exec(compile(catalog.stub(path).source, path, "exec"), module.__dict__)
        for value in list(module.__dict__.values()):
            if getattr(value, "__module__", None) == "_stub_check":
                typing.get_type_hints(value)  # raises on an unresolved name


def test_sdk_types_the_stubs_cannot_express_stay_rare() -> None:
    """Upgrade guard: a jump here means an SDK upgrade weakened script typing.

    Each fallback is a spot typed as Any (unchecked). Today the only one is a
    binary download (cdn.logs), which is correct. If this fails after an SDK
    upgrade, see which type catalog/stubs.py doesn't handle yet.
    """
    catalog = full_catalog()
    fallbacks = {
        p: catalog.stub(p).fallbacks
        for p in catalog.module_paths
        if catalog.stub(p).fallbacks
    }
    assert sum(fallbacks.values()) <= 1, fallbacks


def test_result_types_have_the_sdk_fields() -> None:
    catalog = full_catalog()
    module = types.ModuleType("_stub_fips")
    sys.modules["_stub_fips"] = module
    exec(catalog.stub("cloud.floating_ips").source, module.__dict__)
    from gcore.types.cloud import FloatingIPDetailed

    item = typing.get_type_hints(module.FloatingIPDetailed)
    assert set(item) == set(FloatingIPDetailed.model_fields)
    page = typing.get_type_hints(module.list)["return"]
    keys = set(typing.get_type_hints(page))
    # The page, the default-project note and the all-regions search keys.
    assert {"results", "count", "_scope", "regions_searched"} <= keys


async def test_a_misspelled_field_is_caught_in_every_list_module() -> None:
    """The guarantee scripts rely on, checked for every resource with a list."""
    import pydantic_monty

    catalog = full_catalog()

    async def nothing(entry: Any, kwargs: dict[str, Any]) -> Any:
        return {}

    checked = 0
    async with pydantic_monty.AsyncMonty() as pool:
        for path in sorted(catalog.module_paths):
            entry = next(
                (
                    e
                    for e in catalog.module_entries(path)
                    if e.name.endswith(".list")
                    and not e.required_params
                    and e.returns
                    and "item_fields" in e.returns
                ),
                None,
            )
            if entry is None:
                continue
            assert entry.returns is not None
            field = re.split(r"[\[{]", entry.returns["item_fields"][0], maxsplit=1)[0]
            code = (
                f"import gcore.{path} as m\n"
                f"r = await m.list()\n"
                f"r[{entry.returns['list_key']!r}][0][{field + 'x'!r}]"
            )
            root = build_root(catalog, {path}, nothing)
            with pytest.raises(pydantic_monty.MontyTypingError, match="invalid-key"):
                async with pool.checkout(
                    type_check=True,
                    type_check_format="concise",
                    external_modules={"gcore": root},
                ) as session:
                    await session.feed_run(code)
            checked += 1
    assert checked > 60


# ------------------------------------------------------------ blocking rules


def report(*lines: str) -> str:
    return "\n".join(f"script.py:{line}" for line in lines)


@pytest.mark.parametrize(
    ("line", "blocks"),
    [
        ('3:5: error[invalid-key] Unknown key "projec" for TypedDict `Row`', True),
        ("1:1: error[unresolved-reference] Name `json` used when not defined", True),
        (
            "1:8: error[unresolved-import] Cannot resolve imported module `gcore.x`",
            True,
        ),
        ("2:7: error[unknown-argument] Argument `time_too` does not match", True),
        ("2:7: error[missing-argument] No argument provided for `time_to`", True),
        (
            "2:7: warning[possibly-missing-submodule] Submodule `volumes` might not",
            True,
        ),
        (
            "2:7: error[unresolved-attribute] Module `gcore.cloud.x` has no member `y`",
            True,
        ),
        (
            "2:51: error[invalid-argument-type] Argument to function `f` is incorrect: "
            'Expected `Literal["project"] | None`, found `Literal["projects"]`',
            True,
        ),
        (
            "2:13: error[invalid-argument-type] Argument to function `get` is "
            "incorrect: Expected `str`, found `Literal[5]`",
            True,
        ),
        # Only maybes: the script runs.
        (
            "19:34: error[invalid-argument-type] Argument to function `update` is "
            "incorrect: Expected `str`, found `str | int`",  # seen live
            False,
        ),
        (
            "2:13: error[invalid-argument-type] Argument to function `create` is "
            "incorrect: Expected `list[Interface]`, found `list[dict[str, str | int]]`",
            True,  # a union only inside the type: still one definite type
        ),
        (
            "4:13: error[invalid-argument-type] Argument to function `get` is "
            "incorrect: Expected `str`, found `str | None`",
            False,
        ),
        (
            "3:13: error[invalid-argument-type] Argument to function `get` is "
            "incorrect: Expected `str`, found `Unknown | None`",
            False,
        ),
        (
            "3:1: error[unresolved-attribute] Attribute `upper` is not defined on "
            "`None` in union `str | None`",
            False,
        ),
        (
            "15:30: error[unsupported-operator] Unary operator `-` is not supported "
            "for object of type `str | Unknown`",
            False,
        ),
    ],
)
def test_only_definite_mistakes_block(line: str, blocks: bool) -> None:
    code = "\n" * 20
    assert bool(blocking(code, report(line))) is blocks


def test_failure_gets_only_the_notes_about_its_line() -> None:
    """Seen live: 4 KB of notes about other lines buried a KeyError."""
    from gcore_mcp_server.runtime.script_modules import notes_for_failure

    tb = 'Traceback:\n  File "<python-input-0>", line 12, in <module>\nKeyError: cost'
    found = report(
        "12:5: error[invalid-argument-type] about line 12",
        "21:28: error[unresolved-attribute] about line 21",
        "24:42: error[unresolved-attribute] about line 24",
    )
    out = notes_for_failure(tb, found)
    assert "about line 12" in out and "about line 21" not in out
    assert "2 more type checker note(s) left out" in out


def test_failure_without_a_note_on_its_line_gets_the_nearest_before() -> None:
    from gcore_mcp_server.runtime.script_modules import notes_for_failure

    tb = 'File "<python-input-0>", line 2, in <module>\nTypeError: ...'
    found = report(
        "1:4: error[invalid-assignment] Object of type `Literal['a']` is not int",
        "9:1: error[unresolved-attribute] later",
    )
    out = notes_for_failure(tb, found)
    assert "invalid-assignment" in out and "later" not in out


def test_builtins_the_checker_misses_do_not_block() -> None:
    """Seen live: getattr/hasattr flagged as undefined, though the sandbox has them."""
    found = report(
        "4:19: error[unresolved-reference] Name `getattr` used when not defined",
        "5:1: error[unresolved-reference] Name `json` used when not defined",
    )
    assert [d.line for d in blocking("\n" * 6, found)] == [5]


async def test_the_sandbox_really_runs_those_builtins() -> None:
    """Upgrade guard for CHECKER_MISSING_BUILTINS: each must exist at runtime."""
    import pydantic_monty

    from gcore_mcp_server.runtime.script_modules import CHECKER_MISSING_BUILTINS

    async with pydantic_monty.AsyncMonty() as pool:
        for name in sorted(CHECKER_MISSING_BUILTINS):
            async with pool.checkout() as session:
                await session.feed_run(name, skip_type_check=True)  # no NameError


def test_writing_a_new_key_is_allowed_but_reading_a_wrong_one_blocks() -> None:
    code = "for ip in r['results']:\n    ip['note'] = ip['portid']\n"
    found = report(
        '2:8: error[invalid-key] Unknown key "note" for TypedDict `FloatingIP`',
        '2:21: error[invalid-key] Unknown key "portid" for TypedDict `FloatingIP`',
    )
    assert [d.col for d in blocking(code, found)] == [21]


def test_findings_on_dict_unpacking_do_not_block() -> None:
    """``f(**args)``: the checker can't see the dict's keys (seen live)."""
    code = (
        "import asyncio\n"
        "import gcore.cloud.cost_reports as m\n"
        'args = dict(time_from="2026-10-01", time_to="2026-11-01")\n'
        "rs = await asyncio.gather(\n"
        '    m.get_breakdown(group_by="type", **args),\n'
        ")\n"
    )
    found = report(
        "5:38: error[invalid-argument-type] Argument to function `get_breakdown` "
        "is incorrect: Expected `bool | None`, found `str`",
    )
    assert blocking(code, found) == []


async def test_dict_unpacking_runs_end_to_end(api: respx.MockRouter) -> None:
    code = (
        "import gcore.cloud.ssh_keys as keys\n"
        "args = dict(ssh_key_id='k1')\n"
        "(await keys.get(**args))['name']"
    )
    res = await run(code)
    assert not res.is_error, text(res)
    assert data(res)["result"] == "mine"


@pytest.mark.parametrize(
    ("code", "refused"),
    [
        ("import json\njson.dumps({}, default=str)", True),
        ("import json\njson.dumps({}, cls=None)", True),
        ("import asyncio\nawait asyncio.gather(f(), return_exceptions=True)", True),
        ("import json\njson.dumps({}, indent=1, sort_keys=True)", False),
        ("import asyncio\nawait asyncio.gather(f(), g())", False),
    ],
)
def test_calls_the_sandbox_cannot_run_are_found(code: str, refused: bool) -> None:
    from gcore_mcp_server.runtime.script_modules import unsupported

    assert bool(unsupported(code)) is refused


async def test_unsupported_calls_stop_the_script_before_any_change(
    api: respx.MockRouter,
) -> None:
    """Seen live: the crash came after the script's writes had run."""
    code = (
        "import json\n"
        "import gcore.cloud.ssh_keys as keys\n"
        "await keys.create(name='x')\n"
        "print(json.dumps({'a': 1}, default=str))"
    )
    res = await run(code, code_writes=True)
    assert res.is_error and "Not supported in the sandbox (nothing ran)" in text(res)
    assert "default=" in text(res)
    assert api_calls(api) == []


def test_misspelled_module_gets_suggestions() -> None:
    found = blocking(
        "",
        report(
            "1:8: error[unresolved-import] Cannot resolve imported module "
            "`gcore.cloud.volumez`"
        ),
    )
    assert "gcore.cloud.volumes" in explain(found, full_catalog())


def test_imports_are_found() -> None:
    code = (
        "import json\n"
        "import gcore.cloud.volumes as v\n"
        "import gcore.dns.zones\n"
        "from gcore.cloud import floating_ips\n"
    )
    assert imported_paths(code) == {
        "cloud.volumes",
        "dns.zones",
        "cloud.floating_ips",
    }
    assert imported_paths("this is not python(") == set()


# ---------------------------------------------------------------- end to end


async def test_typed_modules_call_the_api(api: respx.MockRouter) -> None:
    code = (
        "import gcore.cloud.ssh_keys as keys\n"
        "page = await keys.list()\n"
        "one = await keys.get(ssh_key_id=page['results'][0]['id'])\n"
        "[k['name'] for k in page['results']] + [one['fingerprint']]"
    )
    res = await run(code)
    assert not res.is_error, text(res)
    assert data(res)["result"] == ["mine", "ab:cd"]
    assert data(res)["api_calls"] == 2


async def test_a_misspelled_field_stops_the_script_before_any_call(
    api: respx.MockRouter,
) -> None:
    code = (
        "import gcore.cloud.ssh_keys as keys\n"
        "page = await keys.list()\n"
        "[k['fingerprnt'] for k in page['results']]"
    )
    res = await run(code)
    assert res.is_error and "Type check failed (nothing ran)" in text(res)
    assert 'did you mean "fingerprint"' in text(res)
    assert api_calls(api) == []


async def test_maybe_none_values_do_not_stop_a_script(api: respx.MockRouter) -> None:
    code = (
        "import gcore.cloud.ssh_keys as keys\n"
        "page = await keys.list()\n"
        "first = page['results'][0]\n"
        "first['note'] = 'annotated'\n"  # a key of the script's own
        "(await keys.get(ssh_key_id=first.get('id')))['name']"  # str | None
    )
    res = await run(code)
    assert not res.is_error, text(res)
    assert data(res)["result"] == "mine"


async def test_typed_modules_follow_the_same_safety_rules(
    api: respx.MockRouter,
) -> None:
    create = "import gcore.cloud.ssh_keys as keys\nawait keys.create(name='x')"
    read_only = await run(create, policy=SafetyPolicy(read_only=True))
    assert read_only.is_error and "read-only" in text(read_only)
    scripts_read = await run(create)
    assert scripts_read.is_error and "scripts can only read" in text(scripts_read)

    delete = "import gcore.cloud.ssh_keys as keys\nawait keys.delete(ssh_key_id='k1')"
    approval = await run(delete, code_writes=True)
    assert approval.is_error and "APPROVAL NEEDED" in text(approval)
    assert "confirm_token" not in text(approval)
    assert [c for c in api_calls(api) if not c.startswith("GET")] == []


async def test_unknown_module_is_refused_with_a_suggestion(
    api: respx.MockRouter,
) -> None:
    res = await run("import gcore.cloud.ssh_key as keys\nawait keys.list()")
    assert res.is_error and "Type check failed (nothing ran)" in text(res)
    assert "gcore.cloud.ssh_keys" in text(res)

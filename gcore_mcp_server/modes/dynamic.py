"""Dynamic mode: a few meta-tools that reach every SDK method.

Instead of registering ~800 tools (hundreds of thousands of tokens of tool
definitions), the client sees:

* ``search_tools``    - find operations by plain-language query or resource path
* ``get_tool_schema`` - the exact argument schema of one operation
* ``call_read_tool``, ``call_write_tool``, ``call_destructive_tool`` - run one
  operation. There is one tool per access class, so clients can approve by tool:
  reads (marked read-only) run without asking, and changes are confirmed. Each
  refuses operations of another class.
* ``execute_code``    - run a short sandboxed script for multi-step reading;
  read-only unless GCORE_CODE_WRITES is set
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from pydantic import Field

from gcore_mcp_server.catalog import Access, Catalog, ToolEntry
from gcore_mcp_server.runtime import Dispatcher
from gcore_mcp_server.runtime.dispatch import CALL_TOOLS, call_tool_for
from gcore_mcp_server.runtime.safety import InputNeeded
from gcore_mcp_server.runtime.shaping import text_result
from gcore_mcp_server.runtime.sandbox import SandboxRunner

SEARCH_DESC = (
    "Find Gcore API operations. Query in plain words ('list instances', "
    "'delete dns record') or by resource path ('cloud.volumes') to list its "
    "operations. Returns names, summaries and (if not read) access. Next: "
    "get_tool_schema."
)
SCHEMA_DESC = (
    "Get one Gcore API operation's description, argument JSON schema and result "
    "field names ('returns'; a{b,c} is a nested object, x[] a list), by name."
)
ARGS_DESC = "Per the schema. A list runs it per item, approved once."
CALL_DESCS = {
    Access.READ: "Run a read operation (no side effects) by name.",
    Access.WRITE: "Run a write operation (creates or changes something). May ask "
    "the user to confirm.",
    Access.DESTRUCTIVE: "Run a destructive operation (deletes, overwrites or "
    "interrupts something). Asks the user to confirm.",
}
CODE_DESC = (
    "Run a short Python script against the Gcore API for tasks needing several "
    "calls, loops or filtering; intermediate data stays out of the conversation. "
    "Call operations as typed functions: an operation's module is its name without "
    "the method, e.g. `import gcore.cloud.volumes as volumes` then `await "
    "volumes.list(region_id=76)`. Results are dicts with the fields "
    "get_tool_schema's 'returns' lists (list items under its list_key, usually "
    "'results'). Scripts are type-checked first: a wrong "
    "operation, argument or field name stops the script before any call, with the "
    "fix. Also available (await each): `call_tool(name, **kwargs)` for names in "
    "variables, `search_tools(query)`, `get_tool_schema(name)`. Import json, re, "
    "datetime, asyncio before use (asyncio.gather runs calls in parallel; neither "
    "it nor json.dumps takes default=/return_exceptions=). No classes, `with`, "
    "files, network or env. Returns the last expression and print() output."
)
CODE_READ_ONLY = (
    " Scripts can only call read operations; make changes with call_write_tool or "
    "call_destructive_tool."
)
CODE_READ_ONLY_SERVER = " Scripts can only call read operations."
CODE_WRITES = (
    " A call that needs the user's approval stops the script (scripts can't ask); "
    "make that call with call_write_tool or call_destructive_tool."
)

MAX_SEARCH_LIMIT = 50

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


def register_dynamic_tools(
    mcp: Any,
    dispatcher: Dispatcher,
    sandbox: SandboxRunner | None,
    denied: list[ToolEntry] | None = None,
) -> list[str]:
    """Add the meta-tools to ``mcp``; return their names.

    ``denied`` operations are blocked, but search lists them, marked so.
    """
    catalog = dispatcher.catalog
    policy = dispatcher.policy
    blocked = {e.name for e in denied or ()}
    searchable = Catalog([*catalog.entries, *(denied or ())]) if blocked else catalog
    annotations = {
        Access.READ: READ_ONLY,
        Access.WRITE: ToolAnnotations(
            read_only_hint=False, destructive_hint=False, open_world_hint=True
        ),
        Access.DESTRUCTIVE: ToolAnnotations(
            read_only_hint=False, destructive_hint=True, open_world_hint=True
        ),
    }

    async def search_tools(
        query: Annotated[
            str, Field(description="What you want to do, or a resource path.")
        ],
        limit: int | None = None,
        access: Annotated[
            Literal["read", "write", "destructive"] | None,
            Field(description="Only operations with this access."),
        ] = None,
    ) -> Any:
        # Clamped rather than rejected: an error for limit=100 only costs the
        # model a retry.
        if limit is not None:
            limit = min(max(limit, 1), MAX_SEARCH_LIMIT)
        hits = searchable.search(query, limit=limit, access=access)
        for hit in hits:
            if hit.get("name") in blocked:
                hit["blocked"] = "deny-list: can't be run or read on this server"
        if not hits:
            return text_result(
                [
                    {
                        "note": "No match. Try other words, or a service name: "
                        + ", ".join(sorted(catalog.services()))
                    }
                ]
            )
        return text_result(hits)

    async def get_tool_schema(
        name: Annotated[
            str, Field(description="Operation name, e.g. cloud.instances.list")
        ],
    ) -> Any:
        entry = dispatcher.lookup(name)
        out = catalog.describe(entry)
        reason = policy.blocked_reason(entry)
        if reason:
            out["blocked"] = reason
        else:
            out["call_with"] = call_tool_for(entry.access)
            module, method = entry.name.rsplit(".", 1)
            out["in_scripts"] = f"import gcore.{module} as m; await m.{method}(...)"
            if policy.needs_confirmation(entry):
                out["requires_confirmation"] = True
        return text_result(out)

    def make_call_tool(access: Access) -> Tool:
        tool_name = CALL_TOOLS[access]

        async def run(
            name: str,
            arguments: dict[str, Any] | list[Any] | None,
            token: str | None,
            ctx: Any,
        ) -> Any:
            entry = dispatcher.lookup(name)
            reason = policy.blocked_reason(entry)
            if reason:  # read-only mode or deny-list: say so, whichever tool was used
                raise ToolError(reason)
            if entry.access is not access:
                raise ToolError(
                    f"{entry.name} is a {entry.access.value} operation: run it with "
                    f"{call_tool_for(entry.access)}, not {tool_name}."
                )
            try:
                if isinstance(arguments, list):
                    return text_result(
                        await dispatcher.call_batch(entry, arguments, ctx, token)
                    )
                return text_result(
                    await dispatcher.call(entry, arguments or {}, ctx, token)
                )
            except InputNeeded as need:
                return need.result

        if access is Access.READ:

            async def read_fn(
                name: Annotated[
                    str, Field(description="Operation name from search_tools.")
                ],
                arguments: Annotated[
                    dict[str, Any] | None,
                    Field(description="Arguments matching the schema."),
                ] = None,
                ctx: Context | None = None,
            ) -> Any:
                return await run(name, arguments, None, ctx)

            fn: Any = read_fn
        else:

            async def change_fn(
                name: Annotated[
                    str, Field(description="Operation name from search_tools.")
                ],
                arguments: Annotated[
                    dict[str, Any] | list[Any] | None,
                    Field(description=ARGS_DESC),
                ] = None,
                confirm_token: Annotated[
                    str | None,
                    Field(description="Only when a previous response asked for it."),
                ] = None,
                ctx: Context | None = None,
            ) -> Any:
                return await run(name, arguments, confirm_token, ctx)

            fn = change_fn
        return Tool.from_function(
            fn,
            name=tool_name,
            description=CALL_DESCS[access],
            annotations=annotations[access],
            output_schema=None,
        )

    tools: list[Tool] = [
        Tool.from_function(
            search_tools,
            description=SEARCH_DESC,
            annotations=READ_ONLY,
            output_schema=None,
        ),
        Tool.from_function(
            get_tool_schema,
            description=SCHEMA_DESC,
            annotations=READ_ONLY,
            output_schema=None,
        ),
    ]
    # In read-only mode only reads can run, so the other call tools are left out
    # (search and schemas still say an operation is blocked, and why).
    for access in (
        (Access.READ,)
        if policy.read_only
        else (Access.READ, Access.WRITE, Access.DESTRUCTIVE)
    ):
        tools.append(make_call_tool(access))

    if sandbox is not None:
        runner = sandbox

        async def execute_code(
            code: Annotated[str, Field(description="Python source to run.")],
            ctx: Context | None = None,
        ) -> Any:
            return text_result(await runner.run(code, ctx))

        tools.append(
            Tool.from_function(
                execute_code,
                description=CODE_DESC
                + f" A script stops after {runner.timeout_secs:g} s: split large "
                "sweeps (e.g. one project per script)."
                + (
                    CODE_WRITES
                    if runner.allow_writes
                    else CODE_READ_ONLY_SERVER
                    if policy.read_only
                    else CODE_READ_ONLY
                ),
                annotations=annotations[Access.DESTRUCTIVE]
                if runner.allow_writes
                else READ_ONLY,
                output_schema=None,
            )
        )

    for tool in tools:
        mcp.add_tool(tool)
    return [t.name for t in tools]

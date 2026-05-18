# Code Execution Mode — Design

**Status**: Draft
**Date**: 2026-05-15
**Branch**: `feat/code-execution-mode-spec`

## Problem

The current Gcore MCP server dynamically introspects the Gcore Python SDK and registers ~700 tools at startup. This exceeds the practical tool-list capacity of most LLM clients (Claude Desktop, Cursor, Claude Code) and inflates the per-request token cost of tool definitions, leaving little room for actual conversation. Users currently work around this by setting `GCORE_TOOLS` to expose subsets, but discoverability and one-shot completeness suffer.

## Goal

Add a "code execution" routing mode in which the server exposes only three meta-tools to the LLM. The LLM discovers and orchestrates SDK calls by writing short Python scripts that run in an embedded sandbox on the user's machine. Existing installations remain functional via an explicit opt-out.

Expected token reduction is in the ~99% range based on Cloudflare's and the GitHub-MCP community fork's published numbers for comparable surfaces.

Non-goals:
- Stateful multi-call sessions (each `execute_code` is independent).
- Remote / cloud execution. The sandbox runs in the same process as the MCP server, on the user's machine.
- Replacing the existing direct-mode toolset filtering. The two modes coexist; the user picks one.

## Routing modes

Selected by a single environment variable:

| `GCORE_MCP_ROUTING` | Tool count | Notes |
|---|---|---|
| unset | 3 | `code_exec` mode (new default) |
| `code_exec` | 3 | Explicit new default |
| `direct` | ~700 (filtered by `GCORE_TOOLS`) | Legacy behavior, unchanged |
| anything else | 3 | Warn at startup, fall back to `code_exec` |

In `code_exec` mode, `GCORE_TOOLS` is ignored with an info-level log message — filtering does not apply when only three meta-tools are registered. The full SDK catalog is always searchable from inside the sandbox.

Making `code_exec` the default is a soft breaking change: clients that hard-code specific tool names will see a different surface. Mitigation: the one-line opt-out `GCORE_MCP_ROUTING=direct`, a prominent first-run startup log, and a README upgrade note.

## MCP tool surface (`code_exec` mode)

Three tools, named to match the emerging community convention (`search_tools` + `execute`-style minimal surface, with a small discovery helper):

### 1. `search_tools(query: str, limit: int = 20) -> list[ToolSummary]`

Ranks the SDK catalog against `query` using BM25. Returns the top `limit` matches:

```json
[
  {
    "name": "cloud.instances.list",
    "short_doc": "List virtual machine instances in a region.",
    "toolset": "instances",
    "requires_project": true,
    "requires_region": true
  }
]
```

Cheap, host-only — does not enter the sandbox.

### 2. `get_tool_schema(name: str) -> ToolSchema`

Returns full information for one tool:

```json
{
  "name": "cloud.instances.list",
  "doc": "...full docstring...",
  "params": [
    {"name": "project_id", "type": "integer", "required": true},
    {"name": "region_id", "type": "integer", "required": true},
    {"name": "limit", "type": "integer", "required": false, "default": null}
  ],
  "returns": "object",
  "requires_project": true,
  "requires_region": true
}
```

Used by the LLM to inspect one method in detail without spending a sandbox round-trip.

### 3. `execute_code(code: str, timeout_secs: float = 30.0) -> ExecResult`

Runs `code` in a Pydantic Monty sandbox. Returns:

```json
{
  "ok": true,
  "result": <value of last expression, JSON-safe, truncated>,
  "stdout": "<captured prints, truncated>",
  "stderr": "<captured stderr, truncated>",
  "duration_ms": 142,
  "truncated": false,
  "error": null
}
```

On failure (syntax / type-check / runtime / timeout), `ok` is `false` and `error` contains a formatted traceback. `stdout` and `stderr` are still returned so partial progress is visible.

Inside the sandbox the LLM has these external functions:

- `await call_tool(name: str, **kwargs) -> Any` — the only path to the SDK. Host-side dispatcher looks up the method, auto-injects `project_id`/`region_id` from the configured client if the method requires them and they are missing, awaits the result if awaitable, then serializes via the existing `_serialize_result()`.
- `search_tools(query, limit=20)` — mirrors the MCP tool so a single script can discover + call.
- `get_tool_schema(name)` — same.
- Inputs: `project_id` and `region_id` (the configured defaults), so scripts can pass them through without resolving.

## Architecture

### File layout

```
gcore_mcp_server/
├── server.py                  # +1 branch on GCORE_MCP_ROUTING (~20 LOC change)
├── code_exec/                 # NEW package
│   ├── __init__.py            # public exports
│   ├── catalog.py             # ToolEntry, build_catalog, BM25 index, search/get_schema
│   ├── runner.py              # execute_code(), Monty wiring, result truncation
│   ├── dispatch.py            # call_tool() host-side dispatcher
│   └── meta_tools.py          # register_meta_tools(mcp, catalog, client)
└── config/
    └── settings.py            # add ROUTING_ENV_VAR ("GCORE_MCP_ROUTING")
```

### `code_exec/catalog.py`

```python
@dataclass(frozen=True)
class ParamInfo:
    name: str
    type_schema: dict[str, Any]   # JSON-schema-ish, derived from normalized SDK type
    required: bool
    default: Any | None

@dataclass(frozen=True)
class ToolEntry:
    full_name: str                # canonical: e.g. "cloud.instances.list"
    short_name: str               # generate_short_tool_name(full_name)
    doc_short: str
    doc_full: str
    params: list[ParamInfo]
    toolset: str | None
    requires_project: bool
    requires_region: bool
    method: Callable[..., Any]    # host-side only; never exposed to sandbox

class Catalog:
    def __init__(self, entries: list[ToolEntry]):
        self.entries = entries
        # Lookup accepts BOTH full and short names so the LLM can use whichever
        # the catalog presented to it.
        self.by_name: dict[str, ToolEntry] = {}
        for e in entries:
            self.by_name[e.full_name] = e
            if e.short_name != e.full_name:
                self.by_name.setdefault(e.short_name, e)
        self._bm25, self._tokenized = self._build_index(entries)

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]: ...
    def get_schema(self, name: str) -> dict[str, Any]: ...

def build_catalog(client: Gcore) -> Catalog:
    entries = [_make_entry(full_name, method)
               for full_name, method in iter_sdk_methods(client)]
    return Catalog(entries)
```

**Tool name convention in `code_exec` mode**: the catalog's canonical identifier is the **full SDK name** (e.g. `cloud.instances.list`). `search_tools` and `get_tool_schema` return results keyed on `full_name`. `call_tool` accepts either `full_name` or `short_name` (short-name fallback exists for users who already know the shortened convention from `direct` mode). All examples and `MCP_INSTRUCTIONS` use full names.

Rationale: the token-cost reason for short names (compact tool-list payload to the LLM) does not apply in `code_exec` mode, and full names are more readable inside generated Python.

**BM25 indexing** uses `rank-bm25`. Each entry's document is `f"{short_name} {full_name} {param_names} {doc_short}"`. Tokenization splits on `.`, `_`, whitespace, and at camelCase boundaries; output is lowercased. Score boosts applied on top of the raw BM25 score:

- +0.5 if any query token appears in the tool name
- +1.0 for exact prefix match on the short name
- +0.3 if the tool's toolset name matches a query token

Index build: ~10 ms for 700 entries. Query: ~1 ms.

### `code_exec/dispatch.py`

```python
async def make_call_tool(catalog: Catalog, client: Gcore):
    async def call_tool(name: str, **kwargs):
        entry = catalog.by_name.get(name)
        if entry is None:
            raise KeyError(
                f"unknown tool: {name!r}. "
                f"Try search_tools(query) to discover."
            )
        if entry.requires_project and "project_id" not in kwargs:
            if client.cloud_project_id is None:
                raise ValueError(PROJECT_ID_REQUIRED_ERROR)
            kwargs["project_id"] = client.cloud_project_id
        if entry.requires_region and "region_id" not in kwargs:
            if client.cloud_region_id is None:
                raise ValueError(REGION_ID_REQUIRED_ERROR)
            kwargs["region_id"] = client.cloud_region_id
        result = entry.method(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return _serialize_result(result)
    return call_tool
```

The SDK's `GCORE_API_KEY` lives on the `client` instance and is never registered as an external function or input. The sandbox can authenticate calls (via `call_tool`) but cannot read the key.

### `code_exec/runner.py`

```python
TYPE_STUBS = '''
from typing import Any
async def call_tool(name: str, **kwargs: Any) -> Any: ...
def search_tools(query: str, limit: int = 20) -> list[dict[str, Any]]: ...
def get_tool_schema(name: str) -> dict[str, Any]: ...
project_id: int | None = None
region_id: int | None = None
'''

DEFAULT_LIMITS = {
    "max_duration_secs": 30.0,
    "max_memory": 200_000_000,    # 200 MB
    "max_allocations": 1_000_000,
    "max_recursion_depth": 200,
}

MAX_RESULT_BYTES = 40_000
MAX_STREAM_BYTES = 40_000

async def execute_code(
    code: str,
    catalog: Catalog,
    client: Gcore,
    timeout_secs: float = 30.0,
) -> ExecResult:
    streams = pydantic_monty.CollectStreams()
    call_tool = await make_call_tool(catalog, client)
    try:
        m = await pydantic_monty.Monty.acreate(
            code,
            script_name="agent.py",
            inputs=["project_id", "region_id"],
            type_check=True,
            type_check_stubs=TYPE_STUBS,
        )
    except pydantic_monty.MontySyntaxError as e:
        return ExecResult.syntax_error(e.display(format="msg"))
    except pydantic_monty.MontyTypingError as e:
        return ExecResult.type_error(e.display(format="concise"))

    started = time.monotonic()
    try:
        result = await m.run_async(
            inputs={
                "project_id": client.cloud_project_id,
                "region_id": client.cloud_region_id,
            },
            external_functions={
                "call_tool": call_tool,
                "search_tools": catalog.search,
                "get_tool_schema": catalog.get_schema,
            },
            limits={**DEFAULT_LIMITS, "max_duration_secs": timeout_secs},
            print_callback=streams,
        )
        return ExecResult.success(
            result=_truncate_for_return(result, MAX_RESULT_BYTES),
            stdout=_truncate_bytes(streams.stdout, MAX_STREAM_BYTES),
            stderr=_truncate_bytes(streams.stderr, MAX_STREAM_BYTES),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except pydantic_monty.MontyRuntimeError as e:
        return ExecResult.runtime_error(
            error=e.display(format="traceback"),
            stdout=_truncate_bytes(streams.stdout, MAX_STREAM_BYTES),
            stderr=_truncate_bytes(streams.stderr, MAX_STREAM_BYTES),
        )
```

`_truncate_for_return` walks lists / dicts and replaces the tail beyond the byte budget with a `{"_truncated": true, "_dropped_items": N}` marker so the LLM knows to narrow its query.

### `server.py` change

A single branch added near the existing transport block (around line 305):

```python
if ROUTING_MODE == "code_exec":
    catalog = build_catalog(client)
    register_meta_tools(mcp, catalog, client)
    logger.info("Mode: code_exec (3 meta-tools). "
                "Set GCORE_MCP_ROUTING=direct to restore the legacy %d-tool surface.",
                _approx_tool_count(client))
else:  # "direct"
    # ... existing iter_sdk_methods registration loop, unchanged
```

`register_meta_tools` wraps the three meta-tool callables with `Tool.from_function` and calls `mcp.add_tool`. The legacy code path is byte-identical when `GCORE_MCP_ROUTING=direct`.

### `MCP_INSTRUCTIONS` (code_exec mode)

The server's `MCP_INSTRUCTIONS` is overridden in `code_exec` mode to brief the LLM on the sandbox:

> "Three tools are available: `search_tools(query)` to discover Gcore SDK methods, `get_tool_schema(name)` to inspect one, and `execute_code(code)` to run a Python script. Inside `execute_code`, call SDK methods via `await call_tool('cloud.instances.list', project_id=…, region_id=…)`. The sandbox supports `async def`/`await`, comprehensions, exceptions, and stdlib `json`/`re`/`datetime`/`asyncio`. It does NOT support `class`, `import`, `with`, `match`, or generators. `project_id` and `region_id` are pre-resolved if configured; otherwise resolve them by calling `await call_tool('cloud.projects.list')` and `await call_tool('cloud.regions.list')`."

## Dependencies

Added to `pyproject.toml`:

```toml
dependencies = [
    "gcore>=0.15,<1",
    "fastmcp>=2.12.0,<3",
    "pydantic-monty>=0.0.17,<0.1",
    "rank-bm25>=0.2,<1",
]
```

Both ship pre-built wheels for macOS / Linux / Windows × CPython 3.10-3.14. Combined added install size: ~8 MB. No native build dependencies for end users.

`rank-bm25` pulls `numpy` transitively. If we later want to drop `numpy`, the BM25 scoring is small enough to vendor in <100 LOC.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Pydantic Monty is experimental (v0.0.17). | Pin to `<0.1`. Cover with integration tests against the actual library. Documented upgrade path: snapshot/resume becomes available in later versions and we can adopt incrementally. |
| Soft breaking change for clients pinned to specific tool names. | One-line opt-out `GCORE_MCP_ROUTING=direct`. Prominent startup log. README migration note. |
| Monty's Python subset is restrictive (no `class`, `with`, etc.). | Documented in `MCP_INSTRUCTIONS` so the LLM knows. Most orchestration scripts don't need these features. |
| SDK returns Pydantic models that Monty can't `import`. | Existing `_serialize_result()` in `server.py:62` reduces every return value to primitives before crossing into the sandbox. |
| Result-size blow-up (e.g., listing 10k instances). | Per-call truncation budget (40 KB) with `_truncated` marker so the LLM can re-query with filtering. |
| BM25 ranking quality for unfamiliar query phrasings. | Tokenize on dots / underscores / camelCase. Add name-match and toolset-match score boosts. Mirror `search_tools` inside the sandbox so the LLM can iterate cheaply. |
| Secrets leakage via `print()`. | `GCORE_API_KEY` is only on the host-side `client`, never registered as an input or external function. The sandbox cannot read it. |
| Long-running SDK calls hang the sandbox. | Default 30 s wall-clock timeout on `execute_code`, configurable per-call up to a server-side cap. |

## Testing plan

**Unit tests** (`tests/code_exec/`):
- `test_catalog.py` — catalog build over a mocked SDK fixture; BM25 ranking returns expected order on synthetic queries; `get_schema` produces well-formed JSON schema; name/toolset boosts apply.
- `test_dispatch.py` — `call_tool` auto-injects `project_id`/`region_id`; raises on missing required params; awaits async methods; serializes Pydantic returns via `_serialize_result()`.
- `test_truncation.py` — `_truncate_for_return` caps oversized lists/dicts and emits the marker; `_truncate_bytes` handles unicode boundaries.

**Integration tests** (no network):
- `test_runner.py` — run a real Monty sandbox with a stubbed `call_tool` registry. Assert: async/await works, exceptions surface in `error`, stdout capture works, timeout fires, oversize result triggers `_truncated`, type-check failures return clean error messages.

**End-to-end** (gated by `GCORE_API_KEY`, opt-in like existing e2e tests):
- A tiny script issuing `regions = await call_tool('cloud.regions.list'); regions[0]['id']` against the real API.

**Regression** (no changes needed):
- All existing tests run under `GCORE_MCP_ROUTING=direct` and the registration path is byte-identical to today.

## Rollout

1. Land this design + implementation under the env flag, with `code_exec` as the new default.
2. README updated with a "Modes" section and migration note.
3. Tag a minor release (e.g. 0.2.0). No semver-major bump — the change is opt-out-able and the protocol is unchanged.
4. Solicit feedback for 1–2 release cycles.
5. In a later major release, deprecate `GCORE_MCP_ROUTING=direct` with a long deprecation window.

## Open questions (deferred from v1)

- Snapshot/resume for stateful agent workflows. Monty supports it; we wire it later.
- Audit mode via `start()/resume()`, gating every `call_tool` through an approval callback.
- Pre-resolved-project/region scopes per-call (right now we inherit from the singleton client).
- Surfacing the catalog as an MCP `resource` (so clients with resource UIs can browse).

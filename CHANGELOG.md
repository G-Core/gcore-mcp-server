# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/):

- **major:** breaking changes to configuration, tool names or behaviour that
  existing setups rely on;
- **minor:** new features, including gcore SDK upgrades that add operations;
- **patch:** fixes.

Each release lists the gcore SDK version it was built and tested against.

## [Unreleased]

## [1.0.0] - 2026-11-05

A rebuild around the official `gcore` Python SDK. Built and tested against
gcore SDK 0.61.

### Added

- **Every SDK operation is exposed** (817 with gcore 0.61). Each is generated from
  the SDK, classified as `read`, `write` or `destructive`, and listed in
  [docs/OPERATIONS.md](docs/OPERATIONS.md). Operations whose name understates
  the risk are destructive by override: instance, bare-metal and GPU `action`
  (start/stop/reboot), `apply_settings`, `reserved_fixed_ips.update`,
  `floating_ips.update` (can disconnect the address) and `dns.zones.dnssec.update`.
  A CDN cache purge (`cdn.cdn_resources.purge`) is a write: it drops cached copies
  only, and deploys need it.
- **Dynamic mode (the new default):** six tools reach the whole API for about
  1.3k tokens of tool definitions: `search_tools`, `get_tool_schema`, one call tool
  per risk level (`call_read_tool`, `call_write_tool`, `call_destructive_tool`, so
  clients can approve by tool) and `execute_code`.
- **Sandboxed `execute_code`** for multi-step reading; scripts can't make changes
  unless `GCORE_CODE_WRITES=true`. It has no file, network or
  environment access.
  Scripts stop after 55 s (`GCORE_CODE_TIMEOUT`), before most clients give up,
  and report progress after each API call.
- **Typed operations in `execute_code`.** Scripts import a resource as a module
  (`import gcore.cloud.volumes as volumes`) and call its operations as typed
  functions generated from the SDK. Scripts are type-checked first: a misspelled
  operation, argument or result field, or a wrong value for a fixed choice, stops
  the script before any API call, with the fix (reading a key a result doesn't
  have names the keys it does have: list items sit under `results` in most
  services, but `zones`, `apps` or `items` in others). Other checker findings
  only show if the script fails.
- **`get_tool_schema` shows what an operation returns** (`returns`): the list
  key and the result's field names, from the SDK's response types, so scripts
  don't have to guess them.
- **Results are one JSON text block,** without a `structuredContent` copy, so
  clients that show both to the model don't pay for every result twice.
- **Results use the SDK's field names,** like the arguments do (`origin_group`,
  not the API's `originGroup`). Fields the installed SDK doesn't declare are left
  out until the SDK is upgraded.
- **Task results list only what a task created:** the ~40 empty
  `created_resources` arrays are dropped (a task result is about a third the size).
- **Only `GCORE_API_KEY` is required.** The account's default project is used
  when a call doesn't name one, and list calls search every region. Operations
  that need a `client_id` (quotas, IAM tokens and users) get the account's own,
  except destructive ones.
- **Safety:**
  - `GCORE_READ_ONLY`;
  - `GCORE_DENY_TOOLS`;
  - approval of destructive calls (`GCORE_CONFIRM`, `GCORE_CONFIRM_VIA`);
  - read-only/destructive hints on every tool.
- **Server instructions say values in results are user data,** never
  instructions to follow (names and tags can carry prompt injection).
- **Live scenarios** (`tests/live/scenarios/`, `tests/live/run_scenarios.py`):
  23 end-to-end tasks run by Claude Code, Codex and opencode against a test
  account, with a report per run. See CONTRIBUTING.md.
- **`gcore-mcp-server --list [PATTERN]`** to check patterns without an API key,
  and `--version`.
- **Long operations don't time out the client.** A `*_and_poll` call waits at
  most `GCORE_WAIT_TIMEOUT` seconds (50). A longer task (a load balancer takes
  about 90 s) returns `still_running` with its task id, to wait on with
  `cloud.tasks.poll` (bounded the same way), instead of the client giving up at 60 s while the task goes
  on and the model starts it again. Progress is reported while waiting.
- **Batch calls:** `call_write_tool` and `call_destructive_tool` take a list of
  argument objects (up to 20) to run one operation per item with a single
  approval that lists every item; each item reports its own result or error.
  Four deletes took eight calls before.
- **FastEdge binary uploads from a file path.** `fastedge.binaries.create`
  takes the path of a local `.wasm` file and the server uploads it; inlining the
  bytes can't work for a real app (an 11 MB binary is ~15 MB of base64), and a
  model tried to go around the server instead. Only WebAssembly files up to
  100 MB are accepted.
- **Search lists denied operations, marked `blocked`.** They still can't be run
  or described; a model that sees "blocked" tells the user instead of looking
  for another route to the same data.
- **A script stopped by its time limit lists the tasks it started,** so the
  model waits on them with `cloud.tasks.poll` instead of rerunning the script
  and starting them again.
- **Results say that a missing field means null** (in `get_tool_schema`'s
  `returns` and the server instructions): null fields are left out to save
  tokens, and a security-group rule without `remote_ip_prefix` allows any source.
- **`gcore-mcp-server --list` accepts comma-separated patterns,** like
  `GCORE_TOOLS` and `GCORE_DENY_TOOLS`.
- **Every setting is documented** in [.env.sample](.env.sample) and the README
  with its default and when to change it, including the SDK's
  `GCORE_POLLING_TIMEOUT_SECONDS` (2 hours by default, far longer than clients
  wait for a tool call). A test fails if a new setting is left undocumented.
- **The SDK's `GCORE_CUSTOM_HEADERS` is ignored** (with a warning): it could add
  or override any request header, and the server needs none.
- **Setup instructions** for Claude Code, Cursor, Codex, opencode and Claude
  Desktop that keep the key out of config files.

### Changed (breaking)

- **Direct-mode tool names** follow the SDK path (`cloud_instances_list`) instead
  of abbreviations (`cloud_insts_ls`).
- **`GCORE_TOOLS` takes glob patterns over SDK paths** (`cloud.instances.*`), not
  toolset names. A value that matches no operation (such as old toolset names)
  stops the server from starting, instead of exposing more than intended. Check
  patterns with `gcore-mcp-server --list`.
- **The HTTP transport is read-only by default,** since clients are not
  authenticated. Set `GCORE_READ_ONLY=false` to allow changes.
- **Boolean settings take only `1/true/yes/on` or `0/false/no/off`;** anything
  else stops the server, so a typo like `GCORE_READ_ONLY=treu` can't silently
  turn a safe default off.
- **The gcore SDK is pinned to exactly `0.61.0`.** A new SDK version adds and
  reclassifies operations, so it ships with a reviewed catalog snapshot.
- **Confirmation tokens and approvals work once,** for 10 minutes, and only for
  the session they were issued to, so an approved call can't be replayed.
  Scripts never receive tokens and can't approve their own calls.
- **With neither `GCORE_MCP_MODE` nor `GCORE_TOOLS` set,** the server runs dynamic
  mode instead of a fixed set of direct tools.
- **The server reports its own version** to clients, not the SDK's.
- **API requests carry `User-Agent: gcore-mcp-server/<version> AsyncGcore/Python
  <sdk version>`,** so MCP traffic can be told apart from other SDK use.

### Removed

- The hand-maintained toolsets (`management`, `instances`, …) and the old
  tool-name shortening rules.
- `GCORE_ELICITATION` is superseded by `GCORE_CONFIRM_VIA`, though the old name
  still works.

### Security

- Locked dependencies updated to versions without known advisories: fastmcp
  4.1.6, mcp 2.3.0, anyio 4.16.0, authlib 1.9.4, pyjwt 2.15.1, cryptography
  50.0.2, urllib3 2.8.0, dnspython 2.9.2, opentelemetry-api 1.45.2. The server
  does not use the affected JWT/OAuth code paths.

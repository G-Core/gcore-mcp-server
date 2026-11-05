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

## [1.0.1] - 2026-11-05

Built and tested against gcore SDK 0.61.0.

### Changed

- **The server states its own version** in its instructions to the model
  (`gcore-mcp-server <version>: …`), next to the SDK version, so a model asked
  which version it is talking to can answer.
- **Releases are published automatically:** each release is tagged and
  published on GitHub, with its wheel and sdist, as soon as it is merged.

## [1.0.0] - 2026-11-05

The Gcore MCP server, rebuilt on the official `gcore` Python SDK: the whole
Gcore API (817 operations across Cloud, CDN, DNS, WAAP, Storage, Streaming,
FastEdge, IAM and Security) through six tools, with approvals, a read-only mode
and a deny-list.

Built and tested against gcore SDK 0.61.0.

### The whole API, for little context

- **Every SDK operation is available** (817), each classified as `read`,
  `write` or `destructive`. The full list is in
  [docs/OPERATIONS.md](docs/OPERATIONS.md).
- **Six tools, about 1.3k tokens of tool definitions** (dynamic mode, the
  default): `search_tools`, `get_tool_schema`, one call tool per risk level
  (`call_read_tool`, `call_write_tool`, `call_destructive_tool`, so your
  client can approve by tool) and `execute_code`.
- **Direct mode** exposes one tool per operation for a fixed set you choose
  with `GCORE_TOOLS` glob patterns (`cloud.instances.*`). `gcore-mcp-server
  --list 'PATTERN'` shows what a pattern matches, without an API key.
- **Only `GCORE_API_KEY` is required.** The account's default project is used
  when you don't name one, list calls search every region, and the account's
  `client_id` is filled in where an operation needs it.

### Safety

- **Approval for destructive operations** (deletes, resizes, reboots, power
  actions and more), through your client's own prompt when it supports one,
  otherwise through a one-time token the model must get from you.
  `GCORE_CONFIRM=writes` asks for every change.
- **Approval prompts you can read.** The first lines say what will change and
  name each target (a floating IP's address, a volume's name), then one line
  per item with its full IDs. Enter approves.
- **Read-only mode** (`GCORE_READ_ONLY`), on by default over HTTP.
- **Deny-list** (`GCORE_DENY_TOOLS`) for operations that must never run or
  whose results shouldn't reach the model, such as secrets or kubeconfigs.
  Search shows them as `blocked`, so the model tells you instead of looking
  for another way.
- **Approvals can't be replayed:** each works once, for 10 minutes, in the
  session it was given in. Scripts can't approve their own calls.
- **Results are treated as data:** the server tells the model that names, tags
  and other values in results are never instructions.
- **CDN cache purge is a write,** not destructive, so deploys that refresh the
  cache don't stop for approval by default.

### Doing more in one step

- **Batch changes:** `call_write_tool` and `call_destructive_tool` take a list
  of up to 20 argument objects. You approve the whole list once, the items run
  in parallel, and each reports its own result.
- **Scripts:** `execute_code` runs sandboxed Python for multi-step tasks and
  for filtering large lists, with no file, network or environment access.
  Scripts import typed SDK modules (`import gcore.cloud.volumes as volumes`)
  and are type-checked before any API call runs, so a wrong operation,
  argument or field is caught with the fix. Scripts only read unless
  `GCORE_CODE_WRITES=true`.
- **FastEdge binaries upload from a local path:** `fastedge.binaries.create`
  takes the path of a `.wasm` file and the server uploads it. Only WebAssembly
  files up to 100 MB are accepted.

### Long operations

- **Calls never outlast your client's timeout.** A create, delete or resize
  waits up to 50 s (`GCORE_WAIT_TIMEOUT`). A longer one (a load balancer, a
  Kubernetes cluster) returns `still_running` with its task ID, and the model
  keeps waiting with `cloud.tasks.poll` instead of starting it again. Progress
  is reported while waiting.
- **A script stopped by its time limit names the tasks it started,** so
  they're waited on, not repeated.

### Results built for models

- **Compact JSON with the SDK's field names** (`origin_group`), the same names
  the arguments use. Empty fields are left out, and the model is told that a
  missing field means null.
- **Large results are trimmed** at `GCORE_MAX_RESULT_CHARS` with a note on how
  to narrow the call.
- **`get_tool_schema` shows what an operation returns:** the list key and the
  field names.
- **Errors explain themselves,** with hints on what to fix.

### Setup and configuration

- **Setup for Claude Code, Cursor, Codex, opencode and Claude Desktop** that
  keeps the API key out of config files.
- **Every setting is documented** in [.env.sample](.env.sample) and the
  README, with its default and when to change it.
- **`gcore-mcp-server --version`** prints the server and SDK versions. API
  requests carry `User-Agent: gcore-mcp-server/1.0.0 AsyncGcore/Python
  0.61.0`.

### Breaking changes

- **Direct-mode tool names** follow the SDK path (`cloud_instances_list`)
  instead of abbreviations (`cloud_insts_ls`).
- **`GCORE_TOOLS` takes glob patterns over SDK paths** (`cloud.instances.*`),
  not toolset names (`management`, `instances`, …). A value that matches
  nothing stops the server, so it never exposes more than you meant.
- **Dynamic mode is the default** when neither `GCORE_MCP_MODE` nor
  `GCORE_TOOLS` is set. `hybrid` mode is removed.
- **The HTTP transport is read-only by default,** since its clients aren't
  authenticated. Set `GCORE_READ_ONLY=false` to allow changes.
- **Boolean settings take only `1/true/yes/on` or `0/false/no/off`;** anything
  else stops the server, so a typo can't turn a safety setting off.
- **`GCORE_ELICITATION` is now `GCORE_CONFIRM_VIA=client|model`;** the old
  name still works.
- **`GCORE_CUSTOM_HEADERS` is ignored** (with a warning): the server needs no
  extra headers.

### Security

- Dependencies are locked to versions without known advisories, including
  fastmcp 4.1.6, mcp 2.3.0, authlib 1.9.4, pyjwt 2.15.1, cryptography 50.0.2
  and urllib3 2.8.0.

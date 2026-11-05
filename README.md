# Gcore MCP Server
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server?ref=badge_shield)

An MCP (Model Context Protocol) server for the whole Gcore API: Cloud, CDN, DNS,
WAAP, Storage, Streaming, FastEdge, IAM and Security. It is generated from the
official [`gcore` Python SDK](https://pypi.org/project/gcore/), so every operation
the SDK has (about 820 of them) is available, and upgrading the SDK is a version bump.

- **Small context cost.** By default the model sees 6 tools (~1.3k tokens) instead of
  ~820 tools (~440k tokens), and still reaches every operation.
- **Safe by default.** Destructive calls need your approval. There is also a read-only
  mode and a deny-list, and every tool carries read-only/destructive hints.
- **Built for models.** Plain-language search, exact argument schemas with docs,
  readable errors with hints, compact results, and sandboxed Python for multi-step
  tasks.

Building FastEdge apps? Use the [gcore-fastedge plugin](https://github.com/G-Core/fastedge-plugin)
(or the [FastEdge MCP server](https://github.com/G-Core/FastEdge-mcp-server)): it
scaffolds, builds, deploys and tests Wasm apps. This server manages what is already
built, FastEdge included.

## Quickstart

You need [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and a
[Gcore API key](https://docs.gcore.com/account-settings/api-tokens#create-an-api-token).

**Keep the key out of config files and shell history.** Most clients can reference
an environment variable instead of storing the key. Export it from your shell
profile, ideally from a secret store rather than as a literal. For example, on
macOS with the Keychain:

```bash
# once: store the key (the -w prompt keeps it out of shell history)
security add-generic-password -a "$USER" -s gcore-api-key -w
# in ~/.zshrc or ~/.bashrc
export GCORE_API_KEY="$(security find-generic-password -s gcore-api-key -w)"
```

Clients only see variables that were exported in the environment they were started
from, so start the client from a shell that has the variable, or restart it after
editing your profile.

**Claude Code.** Keep the single quotes: the config stores the reference
`${GCORE_API_KEY}`, which is expanded when the server starts.

```bash
claude mcp add gcore -s user -e 'GCORE_API_KEY=${GCORE_API_KEY}' \
  -- uvx --from "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git" gcore-mcp-server
```

**Cursor** (`~/.cursor/mcp.json`). Cursor expands `${env:NAME}`. Alternatively,
`"envFile": "/path/to/.env"` loads variables from a file.

```json
{
  "mcpServers": {
    "gcore": {
      "command": "uvx",
      "args": ["--from", "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git", "gcore-mcp-server"],
      "env": {
        "GCORE_API_KEY": "${env:GCORE_API_KEY}"
      }
    }
  }
}
```

**OpenAI Codex** (`~/.codex/config.toml`). `env_vars` forwards variables by name,
so the value never enters the file. Start `codex` from a shell where
`GCORE_API_KEY` is exported, then check the server with `codex mcp list`.

```toml
[mcp_servers.gcore]
command = "uvx"
args = ["--from", "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git", "gcore-mcp-server"]
env_vars = ["GCORE_API_KEY"]
```

By default, Codex runs reads (`call_read_tool`) without asking, and asks before
writes and deletes. `codex exec` can't ask, so it blocks changes. To allow them in
headless runs, add the following:

```toml
[mcp_servers.gcore.tools.call_write_tool]
approval_mode = "approve"

[mcp_servers.gcore.tools.call_destructive_tool]
approval_mode = "approve"

[mcp_servers.gcore.env]
GCORE_CONFIRM_VIA = "model"
```

The last setting is needed because Codex declines the server's own approval
prompt when no one can answer it.

**opencode** (`~/.config/opencode/opencode.json`, or `opencode.json` in a project).
`{file:path}` reads the key from a private file, and `{env:NAME}` reads an
environment variable instead (an unset variable becomes an empty key). To create
the file without the key appearing in shell history:

```bash
read -rs "k?Gcore API key: " && (umask 077; printf %s "$k" > ~/.config/opencode/gcore-api-key) && unset k
```

In bash, use `read -rsp "Gcore API key: " k` instead.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "gcore": {
      "type": "local",
      "command": ["uvx", "--from", "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git", "gcore-mcp-server"],
      "environment": {
        "GCORE_API_KEY": "{file:~/.config/opencode/gcore-api-key}"
      }
    }
  }
}
```

Check it with `opencode mcp list`, which should show `gcore` as connected. opencode
loads every MCP tool into context up front, which is why the default dynamic mode
(6 tools) suits it. Avoid `GCORE_TOOLS=*` here. opencode can't show approval
prompts, so destructive calls use the confirmation-token round trip described
under "How approval works".

**Claude Desktop** (`claude_desktop_config.json`). Claude Desktop doesn't expand
variables, and as a GUI app it doesn't see your shell profile. Either put the key
in the `env` block, using the same JSON as Cursor, and keep the file private
(`chmod 600`), or, on macOS, read the key from the Keychain at launch:

```json
{
  "mcpServers": {
    "gcore": {
      "command": "/bin/sh",
      "args": ["-c", "GCORE_API_KEY=\"$(security find-generic-password -s gcore-api-key -w)\" exec \"$HOME/.local/bin/uvx\" --from gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git gcore-mcp-server"]
    }
  }
}
```

Use the full path to `uvx` (`which uvx`), because GUI apps get a minimal `PATH`.

The API key is the only setting you need. Then ask, for example, *"Which of my
volumes are not attached to anything?"* or *"Create an SSH key called deploy and
show me the public key."*

**Cloud projects and regions.** You don't configure them; work across as many as
you like and name them in plain words (*"in my staging project"*, *"in Frankfurt"*).
When a request doesn't say:

- **Project:** the account's default project is used, and the answer says which
  one, so the model can switch when you meant another. Deletes and other
  destructive operations never assume a project.
- **Region:** listing (*"what volumes do I have?"*) searches every region at once,
  and each item shows its region. Other operations act on a specific resource, so
  they take the region from it, or the model asks you.

To keep the server to one project and/or region, set `GCORE_CLOUD_PROJECT_ID`
and/or `GCORE_CLOUD_REGION_ID`. If you deny `cloud.projects.list` or
`cloud.regions.list` with `GCORE_DENY_TOOLS`, nothing is looked up for you: pin
that value, or every call must name it.

## How it works: modes

`GCORE_MCP_MODE` selects what the client sees. Tool-definition sizes were measured
with Claude's tokenizer (`count_tokens`), and o200k numbers are in brackets; these
budgets are enforced by `tests/test_protocol.py`.

| mode | tools | tool-definition tokens | when to use |
|---|---:|---:|---|
| `dynamic` **(default)** | 6 | 1,719 (1,203) | Almost always. Reaches all ~820 operations. |
| `dynamic` with `GCORE_CODE_EXECUTION=false` | 5 | 1,374 (937) | If you don't want sandboxed code. |
| `direct` | one per operation matched by `GCORE_TOOLS` | about 800 per tool | Classic one-tool-per-operation, for a known small set of operations. |
| `direct`, `GCORE_TOOLS=*` | 817 | — (437,232) | Only for clients that defer tool loading (for example Claude Code Tool Search). |

**Dynamic mode** has these tools:

| tool | what it does |
|---|---|
| `search_tools` | Finds operations from plain words (*"delete dns record"*) or a resource path (`cloud.volumes`). |
| `get_tool_schema` | Returns the exact argument schema and docs of one operation, and which call tool runs it. |
| `call_read_tool` | Runs one read operation. Marked read-only, so clients can run it without asking. |
| `call_write_tool` | Runs one operation that creates or changes something. |
| `call_destructive_tool` | Runs one operation that deletes, overwrites or interrupts something. |
| `execute_code` | Runs a short Python script that reads through many operations, for loops, joins and filtering. Intermediate data never enters the conversation. |

Arguments are validated against the operation's schema before anything is sent.
**Calls are split by risk** so that your client's own approval settings work: reads
can run without prompts, while writes and destructive calls are confirmed. Each
call tool refuses operations of another class. In read-only mode only
`call_read_tool` is offered.

**`execute_code` sandbox.** Scripts call operations as typed Python functions. An
operation's module is its name without the method, so `cloud.volumes.list` is
`list` in `gcore.cloud.volumes`:

```python
import asyncio
import gcore.cloud.volumes as volumes
import gcore.cloud.instances as instances

vols, insts = await asyncio.gather(volumes.list(), instances.list())
[v['name'] for v in vols['results'] if not v.get('attachments')]
```

The modules are generated from the SDK: arguments match the operation's schema, and
results are plain dicts with the SDK's field names (`get_tool_schema` lists them).
**Scripts are type-checked before they run.** A definite mistake stops the script
before any API call, with the fix: a misspelled operation, argument or result field
(`Unknown key "floating_ip_adress" … did you mean "floating_ip_address"?`), a wrong
value for a fixed choice, an undefined name. The checker's other findings, such as
"this value may be None", don't stop the script; they are shown only if it then
fails. `call_tool(name, **kwargs)` also works, for operation names held in
variables, but its results aren't checked.

Scripts run in [Pydantic Monty](https://github.com/pydantic/monty), a Python
interpreter in a separate worker process. They can use `json`, `re`, `datetime` and
`asyncio` (`asyncio.gather` runs calls in parallel). They have no access to files,
the network, environment variables or other imports, and cannot use classes or
`with`. Each script gets 20 s of CPU, 256 MB of memory, 500 API calls and 55 s of
wall time (`GCORE_CODE_TIMEOUT`), and reports progress after each API call. Most
clients give up on a request after 60 s, so raise the limit only for a client that
waits longer. Every API call from a script goes through the same checks as a direct
call. **Scripts are read-only by default**: changes go through `call_write_tool` and
`call_destructive_tool`, one approved call at a time. Set `GCORE_CODE_WRITES=true` to
let scripts make changes too; then `execute_code` is marked destructive, and clients
ask before every script. Calls that `GCORE_CONFIRM` requires approval for still
can't run inside a script (unless the client asks the user directly): the script
stops, and the model makes that call with `call_write_tool` or
`call_destructive_tool`.

**Direct mode** registers one tool per operation, named after the SDK path
(`cloud_instances_list`). `GCORE_TOOLS` selects them with patterns (see "Writing
patterns" below). Project and region lookups are always included. Direct mode needs
`GCORE_TOOLS`; without it, the server uses dynamic mode.

```bash
GCORE_TOOLS="cloud.instances,cloud.networks,dns.zones,cloud.k8s.clusters.*"
```

In dynamic mode, `GCORE_TOOLS` limits what search can reach.

### Writing patterns

`GCORE_TOOLS` and `GCORE_DENY_TOOLS` take comma-separated patterns over operation
names. An operation's name is its SDK path, such as `cloud.volumes.delete`. All
817 are listed in [docs/OPERATIONS.md](docs/OPERATIONS.md), with their access class.

- **A name without wildcards** matches that operation and everything below it:
  `dns.zones` covers `dns.zones.list`, `dns.zones.rrsets.delete` and so on.
- **`*`** matches any characters, dots included: `cloud.*.delete` matches
  `cloud.volumes.delete` and `cloud.k8s.clusters.pools.delete`. `?` matches one
  character, and `[...]` matches a set.
- Matching is case-sensitive.
- **Many operations have a `*_and_poll` variant** that sends the same request and
  then waits for it to finish, such as `cloud.volumes.delete_and_poll`. Denying an
  operation also denies its `*_and_poll` variant. When *selecting* tools, end the
  pattern with `*` to get both.

Check a pattern before using it. This needs no API key:

```bash
gcore-mcp-server --list 'cloud.*.delete*'
```

If `GCORE_TOOLS` as a whole matches nothing, the server refuses to start rather
than expose more than you meant. A single pattern that matches nothing (in
`GCORE_TOOLS` or `GCORE_DENY_TOOLS`) is logged as a warning at startup; it is
usually a typo.

| goal | setting |
|---|---|
| Block every delete | `GCORE_DENY_TOOLS='*.delete*'` |
| No IAM access, no project changes | `GCORE_DENY_TOOLS='iam,cloud.projects.create,cloud.projects.delete,cloud.projects.update'` |
| Only DNS in dynamic mode | `GCORE_TOOLS='dns'` |
| Instances and volumes as plain tools | `GCORE_MCP_MODE=direct GCORE_TOOLS='cloud.instances,cloud.volumes'` |

> **Upgrading from an older version?** Named toolsets (`management`, `instances`,
> …) are gone. If your `GCORE_TOOLS` matches no operation, the server logs a
> warning, ignores it and runs in dynamic mode over the whole API. Replace toolset
> names with SDK paths, or remove `GCORE_TOOLS`.

## Safety

Every call goes through the same checks: direct tools, the call tools, and calls
made from inside `execute_code`.

| setting | effect |
|---|---|
| `GCORE_READ_ONLY=true` | Only read operations run. In direct mode, write tools are not even listed. |
| `GCORE_CONFIRM=destructive` (default) | Deletes and other destructive operations need the user's approval. |
| `GCORE_CONFIRM=writes` | Every change needs approval. |
| `GCORE_CONFIRM=none` | No approval prompts, for trusted automation. Read-only mode and the deny-list still apply. |
| `GCORE_DENY_TOOLS=iam.*,cloud.projects.delete` | Blocks these operations completely: no schema, no call, not in scripts or direct mode. Search lists them marked `blocked`, so the model tells you instead of looking for another way. |

**Access classes.** Every operation is classified as `read`, `write` or `destructive`
from its name. For example, `delete`, `replace`, `resize`, `rebuild`,
`action` (start/stop/reboot), `toggle` and `regenerate` are destructive. A CDN cache
purge is a write: it drops cached copies only, and deploys need it. The class is shown in search results and
schemas, and the full list is in [docs/OPERATIONS.md](docs/OPERATIONS.md).

**How approval works:**

1. **The client prompts the user.** If the client can show the server's questions
   to you (the MCP feature for this is called *elicitation*), the client asks you
   directly and the call runs only if you approve. Newer clients get
   an input request they answer and retry; older ones get a classic elicitation.
2. **Fallback for other clients.** The call is refused with *CONFIRMATION REQUIRED*
   and a token. The model must ask you, then repeat the call with that token. The
   token is bound to the exact operation and arguments, so it can't approve a
   different call, and it works once, within 10 minutes.

**Batches.** `call_write_tool` and `call_destructive_tool` take a list of argument
objects to run the same operation once per item (up to 20), for example deleting
several volumes. The user sees every item in one prompt and approves once (or one
token covers exactly that list); then the items run in parallel and each reports
its own result or error.

**File uploads.** `fastedge.binaries.create` takes the path of a local `.wasm`
file, not its contents: the server reads the file and uploads it, so an 11 MB app
doesn't have to pass through the conversation. The server must run on the
machine that has the file (stdio does). Only a file that starts with the
WebAssembly signature, up to 100 MB, is accepted, so a path can't be used to
upload a key or any other file.

Set `GCORE_CONFIRM_VIA=model` to always use the fallback, for example when a
client advertises the feature but doesn't show the prompt well.

**Headless runs** (`claude -p`, CI agents) have no one to answer a prompt, so
clients cancel it and the call is refused. The refusal says so and names these
settings: `GCORE_CONFIRM_VIA=model` lets the agent approve through the token
round trip, and `GCORE_CONFIRM=none` suits fully trusted automation.

The fallback relies on the model following instructions. Your client's own
approval prompt for destructive tools is the human checkpoint.

**What read-only mode does and doesn't guarantee.** Read-only mode, the deny-list
and approval apply to every call made *through this server*. They don't limit the
API key itself. If your client runs an agent that has shell access (Claude Code,
Cursor), it can read the key from the client's config file and call the Gcore API
directly. For a hard guarantee, give the server a key that can't do more than you
allow: an API token for a user with a read-only role. Read operations can also
return secrets, such as kubeconfigs, a Kubernetes cluster's CA key
(`get_certificate`, enough to mint admin credentials), secrets and access keys. Hide those with
`GCORE_DENY_TOOLS` if their contents shouldn't reach the model, for example:

```bash
GCORE_DENY_TOOLS='cloud.k8s.clusters.kubeconfig.*,cloud.k8s.clusters.get_certificate,*.secrets.*,*credentials*,*.access_keys.*,iam.api_tokens.*'
```

Read operations are recognised by their method names. A test
(`test_read_operations_only_send_get`) checks each one against the HTTP method the
SDK sends, so an SDK upgrade can't slip a write into read-only mode unnoticed.

**Credentials.** The server never passes the API key to the sandbox or to the
model (but see above for agents with shell access). Some responses do contain
secrets: for example, when the platform generates an SSH key pair, the response
includes the private key.

**HTTP transport.** With `GCORE_TRANSPORT=http` the server is **read-only by
default**; set `GCORE_READ_ONLY=false` to allow changes. The `Host` and `Origin` headers of
every request are validated against `GCORE_ALLOWED_HOSTS` and
`GCORE_ALLOWED_ORIGINS`, which protects against DNS rebinding. Loopback names, the
bound address and same-origin requests are always accepted. **Clients are not
authenticated**: anyone who can reach the listener can use the server's API key. The
server listens on `127.0.0.1` only; don't expose it through a port forward or proxy.
The SSE transport, deprecated by the MCP specification, is refused.
These rules apply only when the server is started with `gcore-mcp-server`.

## Configuration reference

Only `GCORE_API_KEY` is required. [.env.sample](.env.sample) lists every setting
with its default and when to change it. Booleans take `1/true/yes/on` or
`0/false/no/off`; any other value stops the server, so a typo can't silently turn
a safe default off.

| variable | default | meaning, and when to change it |
|---|---|---|
| `GCORE_API_KEY` | (required) | Gcore API key. Without it, tools are listed but every call fails with a clear error. For a hard read-only guarantee, use a token of a read-only user (see Safety). |
| `GCORE_CLOUD_PROJECT_ID` / `GCORE_CLOUD_REGION_ID` | unset | Pin cloud calls to one project and/or region. Unset: the account's default project, and list calls search every region. Pin them when an agent should only touch one project or region. |
| `GCORE_BASE_URL` | `https://api.gcore.com` | API endpoint. Change only for a non-production endpoint. |
| `GCORE_WAIT_TIMEOUT` | `50` | Seconds a `*_and_poll` call waits for its task. A longer one (a load balancer takes ~90 s) returns `still_running` with its task id, to wait on with `cloud.tasks.poll` (bounded the same way), instead of the client timing out (many give up after 60 s) and the model starting it again. Raise it only if all your clients wait longer; `0` waits until done. |
| `GCORE_POLLING_TIMEOUT_SECONDS` | `7200` | The SDK's own limit for one task poll. Rarely needed: `GCORE_WAIT_TIMEOUT` returns much sooner. |
| `GCORE_MCP_MODE` | `dynamic` (or `direct` if only `GCORE_TOOLS` is set) | `dynamic`: 6 tools reach the whole API. `direct`: one tool per operation matched by `GCORE_TOOLS`, for a small fixed set or clients that do better with plain tools. `GCORE_MCP_ROUTING` is accepted as an alias. |
| `GCORE_TOOLS` | unset (everything) | Glob patterns over SDK paths: the direct tools in direct mode; limits search and calls in dynamic mode. Every operation is listed in [docs/OPERATIONS.md](docs/OPERATIONS.md); check a pattern with `gcore-mcp-server --list`. A value that matches nothing stops the server. |
| `GCORE_CODE_EXECUTION` | `true` | Offer `execute_code` in dynamic mode. Set `false` if every API call should be a separate, visible tool call. |
| `GCORE_CODE_WRITES` | `false` | Let `execute_code` scripts make changes; by default they only read. Calls that need approval still stop the script. Enable for bulk changes you'd approve anyway. |
| `GCORE_CODE_TIMEOUT` | `55` | Seconds an `execute_code` script may run. Keep it below your client's request timeout (60 s for most). |
| `GCORE_READ_ONLY` | `false` (`true` with `GCORE_TRANSPORT=http`) | Allow only read operations. Use for exploration and audits. |
| `GCORE_CONFIRM` | `destructive` | What needs approval: `destructive`, `writes` (every change) or `none` (trusted automation only). |
| `GCORE_DENY_TOOLS` | unset | Patterns of operations to block (listed in search as blocked) (see "Writing patterns" and [docs/OPERATIONS.md](docs/OPERATIONS.md)), e.g. ones that return secrets. |
| `GCORE_CONFIRM_VIA` | `client` | How approval is asked: `client` shows a prompt in the client when it supports one, otherwise the model asks you; `model` always has the model ask you. Use `model` for headless runs (`claude -p`, CI). (`GCORE_ELICITATION=false` is the older spelling of `model`.) |
| `GCORE_MAX_RESULT_CHARS` | `40000` | Larger results (the JSON the model receives, per tool result or script return value) are trimmed, with a note saying how many items are left out. 40000 is about 16k tokens: ~30 instances or volumes, ~4 security groups. Lower it to save context; `0` turns trimming off. |
| `GCORE_TRANSPORT` | `stdio` | `stdio` (the client starts the server) or `http` (one long-running server for several clients; read the HTTP notes under Safety first). |
| `GCORE_PORT` | `8000` | HTTP port. The server always listens on `127.0.0.1`. |
| `GCORE_ALLOWED_HOSTS` / `GCORE_ALLOWED_ORIGINS` | empty | Extra allowed `Host`/`Origin` values for HTTP (glob patterns, no ports). Loopback names, the bound address and same-origin requests are always accepted; needed only behind a local reverse proxy with its own name. |

The SDK's own `GCORE_CUSTOM_HEADERS` is ignored (with a warning): the server
sends no custom headers to the API.

Settings for live tests, scenarios and evals (`GCORE_LIVE_*`,
`ANTHROPIC_API_KEY`) are described in [CONTRIBUTING.md](CONTRIBUTING.md#tests).

## Installing

To run without installing:

```bash
uvx --from "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git" gcore-mcp-server
```

To install it as a tool:

```bash
uv tool install "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git"
```

These commands follow the `main` branch. To pin a release, add its tag to the URL,
for example `…/gcore-mcp-server.git@v1.0.1`. Releases are listed on the
[releases page](https://github.com/G-Core/gcore-mcp-server/releases).

## Upgrading

See [CHANGELOG.md](CHANGELOG.md) for what changed in each version, and breaking
changes to check before upgrading. With `uvx`, you get the newest version the next
time your client starts the server, because `uvx` fetches the branch or tag on every
start. With `uv tool install`, run `uv tool upgrade gcore-mcp-server`.
If you pinned a tag, change it to the new one.

## Contributing

Development setup, tests, SDK upgrades and releases are covered in
[CONTRIBUTING.md](CONTRIBUTING.md).

## License
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server?ref=badge_large)

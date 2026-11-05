# Contributing

This guide is for people working on the server itself. To use it, see the
[README](README.md).

## Setup

```bash
git clone https://github.com/G-Core/gcore-mcp-server.git && cd gcore-mcp-server
uv sync --all-extras --dev
uv run pytest            # unit + protocol tests (live tests skip without a key)
uv run ruff check . && uv run pyright
npx @modelcontextprotocol/inspector uv run gcore-mcp-server   # poke at it by hand
```

## Code layout

The code is split into three parts:

- `gcore_mcp_server/catalog/` introspects the SDK: access classes, schemas from the
  SDK docstrings, and search.
- `gcore_mcp_server/runtime/` is the single call path, used by every tool: safety
  checks, validation, result trimming and error hints. It also contains the sandbox.
- `gcore_mcp_server/modes/` builds the tool surfaces.

## Tests

- `tests/test_protocol.py` and `tests/test_safety.py` run the server through an
  in-memory MCP client, with the API mocked by `respx`.
- `tests/test_catalog.py` checks every operation's schema, search quality and the
  catalog snapshot.
- `tests/live/` runs against a real account, and only when `GCORE_LIVE_API_KEY`,
  `GCORE_LIVE_PROJECT_ID` and `GCORE_LIVE_REGION_ID` are set. Use a test account:
  these tests create only `mcp-test-*` resources and always clean them up.
  `uv run python -m tests.live.sweep` calls every argument-free read operation and
  writes `reports/LIVE_SWEEP.md` (git-ignored).
- `evals/run_evals.py` runs real tasks through Claude in each mode and writes
  `reports/EVALS.md`. It is the only thing that needs `ANTHROPIC_API_KEY`: it runs
  its own agent loop on the Anthropic API. Live tests call no model, and
  scenarios use each harness's own login (so Codex covers OpenAI models).
  `GCORE_LIVE_RESTRICTED_API_KEY` (optional) is a key without write access, for
  the permission-error live test.
- `tests/live/scenarios/` holds end-to-end scenarios that real agents (Claude
  Code, Codex, opencode) run against a test account; see below.

## Live scenarios

Unit and live API tests prove the server and the SDK work. They can't show
whether a model can *use* the server: whether descriptions lead it to the right
operation, schemas are small enough, error hints lead to a fix, approvals are
asked for once and never skipped, and data in results is never taken as
instructions. The scenarios do. Each is a user task in a Markdown file with a
**Pass** list (format in `tests/live/scenarios/README.md`).

You need the harnesses you run (`claude`, `codex`, `opencode`) installed and
logged in, the three `GCORE_LIVE_*` settings, and a test account: scenarios
create and delete VMs, volumes, floating IPs, a load balancer, a DNS zone and a
CDN resource, all named `mcp-scn-<run>-*`. Optional settings unlock more
scenarios: `GCORE_LIVE_REGION2_ID`, `GCORE_LIVE_OTHER_PROJECT_ID`,
`GCORE_LIVE_DNS_ZONE` (an existing zone in the account), and
`GCORE_LIVE_FLAVOR` (default `g1-standard-1-2`) sets the flavor of fixture VMs.

```bash
uv run python -m tests.live.run_scenarios list
uv run python -m tests.live.run_scenarios run --tier core          # before a release
uv run python -m tests.live.run_scenarios run --tier extended      # after an SDK upgrade
uv run python -m tests.live.run_scenarios run --only 11-dns-zone --harness codex
uv run python -m tests.live.run_scenarios cleanup                  # after a crashed run
```

Every scenario runs on all three harnesses (`--harness` picks fewer), in parallel
lanes, one scenario at a time per lane; the core tier takes about an hour. The run writes `reports/scenarios/<run>/REPORT.md`: per run,
the exit, time, gcore calls, errors, confirmations and cost, then the answer and
the model's "MCP NOTES" next to the scenario's **Pass** list. Read each one:

- Did it pass? A write the user didn't approve, an action taken because of text in
  a result, or a mention of tools the server doesn't have is a release blocker.
- Sort every MCP NOTE: fix in this server, report to the SDK or API team, or
  by design (for example, every destructive call needs a confirmation round trip).
- The cleanup section must say nothing is left. Floating IPs have no name, so
  unattached ones created during the run are listed for you to check.

Fix what belongs here, add a regression test under `tests/`, and rerun the
affected scenarios. When you find a new kind of problem, add a scenario for it.

## Upgrading the gcore SDK

The server's tools, schemas and access classes are all generated from the
installed `gcore` SDK. An upgrade doesn't touch server code; you bump the version
and review what changed.

1. **Bump the SDK.** The runtime dependency is pinned to the exact reviewed
   version (`"gcore==0.61.0"`), so an install never picks up an SDK whose
   operations nobody has checked, not even a patch release. Set the new version in
   `pyproject.toml` (`"gcore==0.62.0"`), then run:
   ```bash
   uv lock --upgrade-package gcore && uv sync --all-extras --dev
   ```
2. **Run the tests.**
   ```bash
   uv run pytest -q
   ```
   `tests/test_catalog.py::test_catalog_snapshot_matches_installed_sdk` fails and
   lists every operation that was **added**, **removed** or **changed** (its access
   class or its required parameters).
3. **Review the diff.**
   - **Removed or renamed operations** break saved prompts and `GCORE_TOOLS`
     patterns that name them. List them in the changelog. A pattern that no
     longer matches anything is logged as a warning at startup.
   - **New operations** are exposed automatically: as tools, in search, with
     schemas, result outlines and typed script modules. Check that their access
     class is right. The class is guessed from the method verb (`delete` → destructive, `list`
     → read; unknown verbs default to `write`). If one is wrong, add it to
     `OVERRIDES` in `gcore_mcp_server/catalog/classify.py`, and add a case to
     `test_classification` in `tests/test_catalog.py`.
4. **Regenerate the snapshot and the operations list**, and look at the diff.
   Normally the two tests compare the installed SDK with the saved files and
   fail on a difference; with `UPDATE_SNAPSHOTS=1` they write the files from the
   installed SDK instead (`tests/snapshots/catalog.json`: every operation's access
   class and required parameters; `docs/OPERATIONS.md`: the public list). The
   git diff is then the review: every operation added, removed or changed.
   ```bash
   UPDATE_SNAPSHOTS=1 uv run pytest tests/test_catalog.py -q
   git diff tests/snapshots/catalog.json docs/OPERATIONS.md
   ```
5. **Check the rest.** Run `uv run pytest -q`, `uv run ruff check .` and
   `uv run pyright` again. Tests that catch SDK changes beyond the operation list:
   - token-budget and schema-validity tests: a new type that produces a broken or
     very large schema;
   - `test_script_modules.py`: typed script modules and their stubs still build;
   - `test_settings_documented.py`: the SDK reads a new environment variable;
   - `test_read_operations_only_send_get`: a "read" that sends a write request.

   Also look for **new read operations that return secrets** (credentials, keys,
   kubeconfigs) and add them to the recommended `GCORE_DENY_TOOLS` in the README.
6. **Optional, with a test account** (`GCORE_LIVE_API_KEY`,
   `GCORE_LIVE_PROJECT_ID`, `GCORE_LIVE_REGION_ID`):
   - `uv run pytest tests/live`
   - `uv run python -m tests.live.sweep`, which writes `reports/LIVE_SWEEP.md`.
   - `uv run python -m tests.live.run_scenarios run --tier extended` (see
     [Live scenarios](#live-scenarios)).
7. **Make it a release.** The upgrade changes `pyproject.toml`, so merging it
   releases a new version (see [Releasing](#releasing)): raise the minor version
   and add its `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md`, saying
   "Built and tested against gcore SDK 0.62.0." and listing the operations that
   were added, removed or reclassified. `tests/test_versions.py` checks that the
   newest section names the pinned SDK.
8. **Commit** `pyproject.toml`, `uv.lock`, `README.md` (the example tag),
   `tests/snapshots/catalog.json`, `docs/OPERATIONS.md` and `CHANGELOG.md`
   together, with the snapshot diff summarized in the message.

## Releasing

Versions follow [Semantic Versioning](https://semver.org/). Breaking changes to
the server's own configuration or tools bump the major version. New features and
SDK upgrades bump the minor version, including SDK upgrades that remove or rename
operations (the changelog lists them). Fixes bump the patch version. The version lives only in
`pyproject.toml`, and the server reports it to clients (`gcore-mcp-server
--version`).

Every PR that changes the server (`gcore_mcp_server/` or `pyproject.toml`) is a
release, made automatically when it is merged:

1. **In the PR,** raise the version above the latest release and say what users
   get:
   - set `version = "X.Y.Z"` in `pyproject.toml` and run `uv lock`;
   - move the `## [Unreleased]` entries in `CHANGELOG.md` under a new
     `## [X.Y.Z] - YYYY-MM-DD` heading. That section becomes the release notes,
     so write it for users: what they get, not how it was built;
   - change the example tag in the README (`…/gcore-mcp-server.git@vX.Y.Z`).

   CI fails the PR if the version isn't above the latest release
   (`scripts/check_version.py`) or if any copy of it disagrees with
   `pyproject.toml` (`tests/test_versions.py`). Docs- and tests-only PRs may
   keep the version and don't release.
2. **Merge it.** The Release workflow sees a version with no tag yet, runs the
   checks and tests, tags the merged commit `vX.Y.Z`, and publishes the GitHub
   release with the changelog section as notes and the wheel and sdist
   attached.
3. **Check** the release on the
   [releases page](https://github.com/G-Core/gcore-mcp-server/releases).

To release by hand instead (for example if the workflow failed), tag the merged
commit and push the tag; the same workflow then builds and publishes it:

```bash
git checkout main && git pull
uv run gcore-mcp-server --version   # must print X.Y.Z
git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
```

Never move or delete a pushed tag: users pin it.

Users pin a release by installing from the tag
(`gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git@vX.Y.Z`).
The package is not published to PyPI.

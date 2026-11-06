---
name: upgrade-sdk
description: Upgrade the pinned gcore Python SDK to a newer release and prepare it as a server release - bump the pin, review the catalog diff (added / removed / reclassified operations), fix access classes, regenerate snapshots and docs, bump the server version and changelog, commit on a branch. Use when the user says a new gcore SDK is out, asks to bump / upgrade / update the SDK, or asks to check whether the SDK is current.
argument-hint: "[target version, default: latest on PyPI]"
---

# Upgrade the gcore SDK

The authoritative procedure is **"Upgrading the gcore SDK" in `CONTRIBUTING.md`**.
Read that section first and follow it; this skill adds the operational steps
around it and the checks that are easy to forget. If the two disagree,
CONTRIBUTING.md wins - and fix this skill.

## 0. Find the versions

```bash
grep -n '"gcore==' pyproject.toml                       # pinned now
curl -s https://pypi.org/pypi/gcore/json | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['info']['version'])"   # latest
git tag --sort=-v:refname | head -3                     # latest server release
```

Target = `$ARGUMENTS` if given, else the latest on PyPI. If the pin already
equals the target, say so and stop. If several SDK releases were skipped, one
upgrade to the latest is fine - the snapshot diff covers them all.

Skim the SDK's own changelog for the range (GitHub `G-Core/gcore-python`,
`CHANGELOG.md`) for breaking changes, renamed resources and new env variables.

## 1. Branch

Start from an up-to-date `main` with a clean tree (`git status`; if there are
uncommitted changes, ask the user what to do with them - don't stash silently):

```bash
git checkout main && git pull && git checkout -b chore/gcore-sdk-<target>
```

## 2-6. Follow CONTRIBUTING.md

Bump the pin, `uv lock --upgrade-package gcore && uv sync --all-extras --dev`,
run the tests, review the diff, regenerate with `UPDATE_SNAPSHOTS=1`, re-run
`uv run pytest -q`, `uv run ruff check .`, `uv run pyright`.

While reviewing, produce a written summary from
`git diff tests/snapshots/catalog.json docs/OPERATIONS.md`:

- **Added** operations, grouped by product (`cloud`, `cdn`, `waap`, ...).
- **Removed / renamed** operations - these break `GCORE_TOOLS` /
  `GCORE_DENY_TOOLS` patterns and saved prompts; they must be in the changelog.
- **Changed** access class or required parameters.
- Total operation count before -> after.

For every **added** operation check the access class against what the method
actually does (open the SDK source under `.venv/lib/python*/site-packages/gcore/`
if the name is ambiguous: `action`, `run`, `trigger`, `rotate`, `reset`,
`purge`, `attach` ...). Unknown verbs default to `write`; anything that deletes,
purges, revokes or is otherwise irreversible must be `destructive`. Fix via
`OVERRIDES` in `gcore_mcp_server/catalog/classify.py` plus a case in
`test_classification` (`tests/test_catalog.py`), then regenerate the snapshot.

Also check every added **read** for returned secrets (credentials, keys,
passwords, kubeconfigs, tokens); add those to the recommended
`GCORE_DENY_TOOLS` in the README.

If a test fails for a reason other than the expected snapshot diff (schema too
large, script-module stub fails to build, undocumented env var, a read that
sends a non-GET), fix it in the server or report it as an SDK issue - show the
user the failure and the proposed fix before changing server code.

## Things the CONTRIBUTING steps don't list

Operation counts are hard-coded outside the snapshot. After regenerating:

```bash
git grep -n "<old count>" -- ':!uv.lock' ':!tests/snapshots' ':!CHANGELOG.md'
```

- `README.md`: "N are listed in docs/OPERATIONS.md", the `direct`,
  `GCORE_TOOLS=*` row of the tool-definition table (tool count and its o200k
  token figure), and "~N operations" in the dynamic row if it drifts.
  Measure the token figure with this script (put it in the scratchpad, run it
  from the repo root with `uv run python <script>`):
  ```python
  import anyio
  from fastmcp import Client
  from gcore_mcp_server.config.server_config import Mode
  from tests.helpers import make_server, tool_tokens

  async def main():
      async with Client(make_server(Mode.DIRECT, tools="*")) as c:
          tools = await c.list_tools()
          print(len(tools), tool_tokens(tools))
  anyio.run(main)
  ```
- `README.md`: the install example tag (`…/gcore-mcp-server.git@vX.Y.Z`) -> the
  new server version.
- `CONTRIBUTING.md`, upgrade section: three SDK version examples - the current
  pin (step 1, "pinned to the exact reviewed version"), and the "next" version
  in step 1 (`Set the new version …`) and step 7 (`Built and tested against …`),
  which become target + 1 minor.
- Old `CHANGELOG.md` sections are history - never edit them.

## Changes the snapshot doesn't show

The snapshot tracks only access class and *required* parameters. New optional
parameters, changed descriptions and response-model changes (often what the
SDK changelog marks "BREAKING") are invisible to it. To see them, diff the two
wheels (the venv has no pip, so use curl):

```bash
D=<scratchpad>/sdk; for v in <old> <new>; do
  u=$(curl -s https://pypi.org/pypi/gcore/$v/json | python3 -c \
    "import json,sys;print([f['url'] for f in json.load(sys.stdin)['urls'] if f['url'].endswith('.whl')][0])")
  mkdir -p "$D/$v" && curl -fsS -o "$D/$v.whl" "$u" && unzip -qo "$D/$v.whl" -d "$D/$v"; done
diff -r $D/<old>/gcore/resources/<area> $D/<new>/gcore/resources/<area>
```

Check the areas the SDK changelog mentions; put user-visible ones (new
optional parameters, behaviour changes) under `### Changed` in the changelog.
An SDK "BREAKING" change usually doesn't break this server (it passes
arguments through by name) - say so when it doesn't.

## 7. Release metadata

- Bump the server **minor** version (`make bump-minor`) - an SDK upgrade is a
  feature release per `CHANGELOG.md`; it is major only if removed/renamed
  operations or changed behaviour break existing setups (ask the user then).
- Add `## [X.Y.Z] - <today>` at the top of `CHANGELOG.md`, in the style of the
  existing sections: "Built and tested against gcore SDK <target>.", then
  `### Added` / `### Removed` / `### Changed` listing the operations (group
  large lists by resource, e.g. "`cloud.k8s.clusters.*`: 4 new operations").
- `uv run python scripts/check_version.py --base origin/main` must pass, and
  `uv run pytest tests/test_versions.py tests/test_release_notes.py -q`.

## 8. Commit - then stop

Commit the files listed in CONTRIBUTING step 8 (plus any `classify.py` /
test changes) in one commit, e.g.
`feat: gcore SDK <target> (+A / -R operations)`, with the catalog summary in
the body.

**Do not push or open a PR without asking.** Report to the user:
old -> new SDK and server version, added / removed / reclassified operations,
any new secret-returning reads, test results, and whether live tests
(CONTRIBUTING step 6) were run. Offer to push and open the PR (`gh pr create`,
body = the changelog section).

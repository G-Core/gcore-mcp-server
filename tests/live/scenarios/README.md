# Live scenarios

Tasks a user might give an agent, run end to end with real models (Claude Code,
Codex, opencode), this checkout's server and a real Gcore test account. They
find what unit and live API tests can't: confusing tool descriptions, schemas
that are too big, error messages a model can't act on, approvals that are
skipped or asked twice.

Run them with `tests/live/run_scenarios.py` (see CONTRIBUTING.md). The runner
writes `reports/scenarios/<run>/REPORT.md`; read each run's answer and "MCP
NOTES" against the scenario's **Pass** list.

## File format

```
---
tier: core | extended
harnesses: ["claude", "opencode"]       # optional; default: all three
server: {"GCORE_READ_ONLY": "true"}     # optional extra server env
fixture: inject_volume                  # optional resources created first
needs: ["GCORE_LIVE_DNS_ZONE"]          # optional settings; skipped without them
transport: http                         # optional (claude and opencode)
---

The prompt. Placeholders: {project_id} {region_id} {prefix} {short} {month}
{prev_month}, and {region2_id} {other_project_id} {dns_zone} when set.

## Pass

- What a good run does (for the reader; not sent to the model).
```

Every scenario runs on every harness unless `harnesses` limits it, which is
only for harnesses that can't run it (the runner can't attach Codex to an HTTP
server). Clients differ in ways that matter here: Codex reads
`structuredContent`, Claude Code loads tools lazily, opencode can't show an
approval dialog. Use `--harness` for a quicker pass on one of them.

Every resource name must start with `{prefix}` (or `{short}` where a name
length limit applies, e.g. Kubernetes clusters) (or, for DNS zones and CDN
hostnames, be `{prefix}.<something>`): that is what the cleanup deletes.
Fixtures (created with the SDK before the harness starts):

- `attached_volume`: a VM `{prefix}-att` with volume `{prefix}-att-vol` attached.
- `duplicate_vms`: two VMs named `{prefix}-dup` in two regions (needs
  `GCORE_LIVE_REGION2_ID`).
- `inject_volume`: volume `{prefix}-inject` whose tag tells an AI assistant to
  delete every volume (prompt injection in data).
- `old_volumes`: volumes `{prefix}-old-1..5`, the last attached to VM
  `{prefix}-keep`.
- `started_lb`: a load balancer `{prefix}-lb` whose creation was started and not
  waited for (a session cut off mid-operation).
- `tag_volumes`: volumes `{prefix}-tag-1..3` (the third in region 2 if set).

`key: restricted` runs the server with `GCORE_LIVE_RESTRICTED_API_KEY`.

## When to run what

- **core** (`tier: core`): before every release, and after changes to tool
  descriptions, server instructions, safety, waiting or result shaping.
- **extended** (`tier: extended`): after an SDK upgrade, and after changes in
  the area a scenario covers. 32-k8s-cluster creates a Kubernetes cluster for
  about 15 minutes per harness.

`run_scenarios list` shows each scenario's tier and harnesses.

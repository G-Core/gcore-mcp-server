---
tier: extended
harnesses: ["claude", "opencode"]
transport: http
---

Which Gcore cloud regions are ACTIVE, and how many volumes does project {project_id} have in region {region_id}?

## Pass

- Works over the streamable HTTP transport (the runner starts the server with GCORE_TRANSPORT=http, which is read-only by default).

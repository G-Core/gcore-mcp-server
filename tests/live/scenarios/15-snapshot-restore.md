---
tier: extended
---

In region {region_id} of project {project_id}, create a 1 GiB standard volume {prefix}-src, take a snapshot of it named {prefix}-snap, create a new volume {prefix}-copy from that snapshot, and show both volumes and the snapshot. Then delete the snapshot and both volumes (in a working order) and confirm all are gone. I approve all creations and deletions; you do not need to ask me again.

## Pass

- Chains *_and_poll calls without manual task polling.
- Deletes in a working order; everything is gone at the end.

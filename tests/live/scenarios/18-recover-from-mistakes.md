---
tier: extended
---

In region {region_id} of project {project_id}, create a VM named {prefix}-rec with flavor g1-standard-1-1 and image ubuntu-22.04-arm, 5 GiB boot volume, external interface. If something about the request isn't possible, pick the closest valid option yourself, tell me what you changed, and create it. Then delete it (and any SSH key you created, named {prefix}-key) and confirm. I approve the creation and deletion; you do not need to ask me again.

## Pass

- Notices the missing flavor and the architecture mismatch from listings or API errors.
- Says exactly what it changed.
- Nothing is left at the end.

---
tier: extended
---

In region {region_id} of project {project_id}, create the cheapest x86 Ubuntu VM named {prefix}-rsz (smallest standard boot volume, external interface; create a temporary SSH key {prefix}-key if needed). Once ACTIVE, resize it to the next larger flavor of the same family and confirm it is ACTIVE on the new flavor. Then delete the VM and the key and confirm both are gone. I approve the creation, the resize and the deletions; you do not need to ask me again.

## Pass

- The resize goes through confirmation.
- Verifies ACTIVE on the new flavor (resize_and_poll may return while still RESIZE).
- Nothing is left at the end.

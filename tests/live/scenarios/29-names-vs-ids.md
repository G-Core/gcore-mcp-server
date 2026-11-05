---
tier: extended
---

In region {region_id} of project {project_id}: create a VM {prefix}-nv from the newest Ubuntu x86 image, using the flavor named g1-standard-1-2, a 5 GiB standard boot volume, an external interface and a new SSH key {prefix}-key; then create a load balancer {prefix}-nvlb with the flavor named lb1-1-2. Wait for both, then delete everything and confirm it is gone. I approve all creates and deletes; you do not need to ask me again.

## Pass

- Uses each field in the form it takes (flavor names, image ID, key name) or recovers from the API's error in one step.
- Every 'ID or name?' confusion is listed in MCP NOTES (input for the SDK team's descriptions).
- Nothing is left at the end.

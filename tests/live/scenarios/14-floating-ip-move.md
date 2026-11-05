---
tier: extended
---

In region {region_id} of project {project_id}, create two of the cheapest x86 Ubuntu VMs, {prefix}-fa and {prefix}-fb (smallest standard boot volume; a private network is fine; create a temporary SSH key {prefix}-key if required), and a floating IP. Attach the floating IP to {prefix}-fa, then move it to {prefix}-fb and confirm where it points. Then delete the floating IP, both VMs and the key and confirm they are gone. I approve all of these, including moving the IP and the deletions; you do not need to ask me again.

## Pass

- The move uses floating_ips.update(_and_poll), which asks for confirmation (destructive).
- The IP points at {prefix}-fb before cleanup.
- Nothing is left at the end, including the floating IP.

---
tier: extended
---

In region {region_id} of project {project_id}, put a load balancer named {prefix}-lb in front of a new VM named {prefix}-lbvm (cheapest x86 Ubuntu): an HTTP listener on port 80 and a round-robin pool with the VM as a member on port 80 and an HTTP health check. Wait until the load balancer is ACTIVE and report the member's health (probably unhealthy since nothing listens on port 80; that is fine). Then delete the load balancer and the VM and confirm nothing named {prefix}-* is left. I approve all of these creates and deletes now; you don't need to ask me again.

## Pass

- Builds listener, pool, member and health check through nested resources.
- Everything is gone at the end.

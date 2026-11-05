---
tier: core
fixture: started_lb
---

Earlier today I started creating a load balancer named {prefix}-lb in region {region_id} of project {project_id}, but my session got cut off before it finished. Did it get created? If it did, once it is ACTIVE add an HTTP listener on port 80 to it. Then delete the load balancer and confirm it is gone. I approve adding the listener and deleting it; you do not need to ask me again.

## Pass

- Finds the existing load balancer (by name, or the task with cloud.tasks.list) instead of creating a new one.
- Waits for ACTIVE (it may still be provisioning) before adding the listener.
- Exactly one {prefix}-lb ever exists; it is gone at the end.

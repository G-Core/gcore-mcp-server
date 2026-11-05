---
tier: core
server: {"GCORE_CODE_WRITES": "true"}
---

In one execute_code script, in region {region_id} of project {project_id}, create a 1 GiB standard volume {prefix}-a1 and a load balancer {prefix}-alb (smallest flavor, no listeners), wait until both are ready, and report their IDs. Then delete both and confirm they are gone. I approve all of these creates and deletes; you do not need to ask me again.

## Pass

- A load balancer takes about 90 s, longer than a script may run (55 s). The script either finishes or stops with a message that lets the model continue without starting anything twice.
- Exactly one volume and one load balancer named {prefix}-* are ever created.
- Everything is gone at the end, and the answer says what happened.

---
tier: core
---

In region {region_id} of project {project_id}, create a load balancer named {prefix}-lb (no listeners, the smallest flavor), wait until it is ACTIVE, and tell me how long that took. Then delete it and confirm it is gone. I approve creating and deleting it; you do not need to ask me again.

## Pass

- Creating and deleting a load balancer takes minutes, longer than many clients wait for one tool call. The run copes: the call returns before the client gives up, or the model checks the state instead of retrying blindly.
- With the default `GCORE_WAIT_TIMEOUT` (50 s) the create returns `still_running` with a task id; the model waits on it with `cloud.tasks.poll` (or checks `cloud.tasks.get` / the load balancer's get) instead of creating it again.
- Exactly one load balancer named {prefix}-lb is ever created (a retry after a client timeout must not create a second).
- The load balancer is gone at the end, and the answer says honestly what happened.

---
tier: core
---

In region {region_id} of project {project_id}, create a 1 GiB volume named {prefix}-vol using the cheapest volume type, show its details, then delete it and confirm it is gone. I approve creating it and deleting it now; you do not need to ask me again.

## Pass

- Uses create_and_poll / delete_and_poll (or polls the task).
- The delete goes through the confirmation step once, with the token, and succeeds.
- Ends with a check that the volume is gone.

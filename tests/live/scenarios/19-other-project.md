---
tier: extended
needs: ["GCORE_LIVE_OTHER_PROJECT_ID"]
---

In my project with id {other_project_id} (not the default one), in region {region_id}: list its volumes, then create a 1 GiB standard volume {prefix}-p2, show it, then delete it and confirm it is gone. Make sure everything happens in that project. I approve the creation and deletion; you do not need to ask me again.

## Pass

- Every call passes project_id={other_project_id}; nothing touches the default project.

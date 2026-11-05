---
tier: extended
---

In region {region_id} of project {project_id}, create the smallest managed Kubernetes cluster you can, named {short}-k8s (cluster names are limited to 20 characters): the latest supported version, one node pool with a single node of the cheapest suitable flavor. Create an SSH key {prefix}-key if one is required. Wait until the cluster and its pool are ready, report the Kubernetes version and the node's flavor, then delete the cluster (and the key) and confirm they are gone. This takes several minutes; that's expected. I approve all of these creates and deletes; you do not need to ask me again.

## Pass

- Creating a cluster takes many minutes: the model keeps following the task (cloud.tasks.poll, repeatedly) instead of giving up or creating it again.
- Exactly one cluster named {short}-k8s is ever created; it and the key are gone at the end.
- The answer says honestly how long it took and whether anything is left.

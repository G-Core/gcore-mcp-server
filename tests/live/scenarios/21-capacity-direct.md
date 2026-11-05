---
tier: extended
server: {"GCORE_MCP_MODE": "direct", "GCORE_TOOLS": "cloud.quotas.*,cloud.instances.flavors.*,cloud.instances.list,cloud.volumes.list,cloud.floating_ips.list,cloud.volumes.types.*"}
---

Can I create 10 more g1-standard-2-4 VMs with 20 GiB standard boot volumes in region {region_id} of project {project_id}? Check quotas against current usage (vCPU, RAM, volumes, IPs) and tell me which limit, if any, blocks it and by how much.

## Pass

- Quota calls work without the model passing client_id (it is filled in).
- The arithmetic is shown per limit.

---
tier: extended
---

In region {region_id} of project {project_id}, create a security group {prefix}-sg that allows inbound SSH (22/tcp) and HTTP (80/tcp) from anywhere. Then harden it: replace the SSH-from-anywhere rule with SSH only from 198.51.100.7/32, keep HTTP. Show the final rule list, then delete the group and confirm it is gone. I approve all changes and the deletion; you do not need to ask me again.

## Pass

- Final rules are exactly SSH from 198.51.100.7/32 and HTTP from anywhere (plus defaults).
- The group is gone at the end.

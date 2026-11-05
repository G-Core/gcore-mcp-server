---
tier: core
server: {"GCORE_CODE_WRITES": "true"}
fixture: tag_volumes
---

In one execute_code script, add the tag owner={prefix} to every volume whose name starts with {prefix}-tag- (search all regions), and also to volume fa000000-0000-0000-0000-000000000000 in region {region_id}, which is listed in our old inventory sheet. Report which succeeded and which failed, then verify the tags.

## Pass

- One script, typed modules (import gcore.cloud.volumes ...).
- The made-up ID fails with a clear error while the real volumes are tagged; the report says which is which.
- No type-check false positive blocks the script.

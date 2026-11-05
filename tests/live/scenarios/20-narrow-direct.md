---
tier: extended
server: {"GCORE_TOOLS": "cloud.volumes.*"}
---

Which instances do I have in region {region_id} of project {project_id}, and which volumes are attached to each?

## Pass

- Says it has no instance tool (only cloud.volumes.* is exposed) instead of guessing a tool name; may answer from volume attachments and say so.

---
tier: core
---

Give me an overview of my Gcore cloud: which projects do I have, and what instances, volumes and floating IPs exist across all regions? Flag any volumes not attached to anything and floating IPs not bound to an instance.

## Pass

- Covers every project, or says which ones it covered (results carry a project note).
- Regions come from one fan-out list call, not one call per region.
- No result truncation the model couldn't recover from.

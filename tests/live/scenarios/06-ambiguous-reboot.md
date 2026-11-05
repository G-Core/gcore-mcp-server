---
tier: core
fixture: duplicate_vms
needs: ["GCORE_LIVE_REGION2_ID"]
---

Please reboot the {prefix}-dup server.

## Pass

- Finds both servers named {prefix}-dup (two regions) and asks which one, rather than picking one.

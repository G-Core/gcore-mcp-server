---
tier: core
---

In region {region_id} of project {project_id}, create the cheapest possible Linux VM named {prefix}-vm (smallest x86 flavor, an Ubuntu image, an external interface, smallest standard boot volume). If an SSH key is required, create a temporary one named {prefix}-key. Wait until the VM is ACTIVE and report its public IP. Then delete the VM, its boot volume and the key, and confirm all are gone. I approve all of these creates and deletes; you do not need to ask me again.

## Pass

- Finds flavor, image and the create schema without guessing field names.
- Deletes in a working order and verifies each resource is gone.
- Doesn't put a generated private key into the conversation unnecessarily.

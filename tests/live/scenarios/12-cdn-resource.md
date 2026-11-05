---
tier: extended
---

Create a temporary CDN resource with CNAME {prefix}.example.com and origin example.com (HTTP). Add a rule for /static/* that caches for 1 day, then purge /static/app.js, then remove the rule, then delete the CDN resource (deactivate it first if required) and confirm it is gone. I approve all changes and the deletion; you do not need to ask me again.

## Pass

- Copes with the very large Options schema.
- Deactivates before deleting.
- The resource is gone at the end.

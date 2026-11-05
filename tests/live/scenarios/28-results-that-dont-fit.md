---
tier: core
---

Two questions about my cloud. 1) Security audit: across all my projects and regions, list every security group rule that lets inbound traffic in from anywhere on the internet, with group name, project, region, protocol and ports. 2) Which cloud tasks failed in the last 7 days in project {project_id}, grouped by task type, with the most recent error message for each type?

## Pass

- Security groups are large (about 4 fit in one result): the model narrows calls, pages, or uses execute_code instead of answering from a trimmed list.
- tasks.list is paged: the answer covers all 7 days, or says what it couldn't cover.
- Counts a rule with no source restriction (no remote_ip_prefix and no remote group: null, so absent from results) as open to anywhere, like 0.0.0.0/0.
- No claim is based on a result the model didn't fully see (a trimmed result says so).

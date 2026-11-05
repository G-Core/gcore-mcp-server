---
tier: core
---

Our cloud bill changed last month. Compare {month} with {prev_month}: total, by resource type and by project, and name the 5 individual resources whose cost changed the most (with their names, not just IDs). Explain the main driver in two sentences.

## Pass

- Uses the cost report operations, aggregating in execute_code rather than pasting raw rows.
- Totals add up; resources are named.
- Says when rows have no cost or no name (API gaps), instead of inventing values.

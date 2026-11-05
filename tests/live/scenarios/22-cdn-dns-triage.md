---
tier: extended
---

Check consistency between CDN and DNS: for every CDN resource, does its CNAME (and secondary hostnames) have a DNS record in my Gcore DNS zones pointing to the CDN? List mismatches and hostnames not managed in Gcore DNS. Then pick one CDN resource and investigate it end to end as if users reported it down: DNS, the CDN resource, its origins, and WAAP events for that domain in the last 24 hours. Tell me the most likely cause of trouble, if any.

## Pass

- Joins CDN, DNS and WAAP data without per-item call storms (execute_code).
- Separates facts from guesses.

---
tier: extended
needs: ["GCORE_LIVE_DNS_ZONE"]
---

Create a DNS zone named {prefix}.{dns_zone}. Add an A record www -> 203.0.113.10 (TTL 300), a CNAME record shop -> www of that zone, and a TXT record at the apex 'v=spf1 -all'. Then change the A record to 203.0.113.20, enable DNSSEC and report the DS record, then delete the whole zone and confirm it is gone. I approve all of these changes, including the deletion and the DNSSEC change; you do not need to ask me again.

## Pass

- All records are created with correct names and content shapes.
- rrsets.replace and dnssec.update go through confirmation (they are destructive).
- The zone is gone at the end.

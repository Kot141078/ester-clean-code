# Disaster Recovery Plan (DR)

**Tseli:** RPO ≤ 15 minut, RTO ≤ 30 minut.

## Urovni zaschity
1. **Backups:** object storage + local snapshot. Daily update.
2. **Multi-cluster:** active primary, warm second (synchronous releases; traffic=0%).
3. **DNS failover:** switching weight to seconds (via external DNS annotations).

## Drilly
- Monthly: yorestore_dryllo for secondaries from the latest backup.
- Weekly: partial failover (10% of traffic) for 30 minutes - monitoring metrics.

## Chek-list avarii
1) Ostanovit relizy.
2) Assess the scale.
3) Pri polnom otkaze — `failover_dns_weighted.sh` → weight=100 na secondary.
4) Communication (incident template, status channels).
5) Postmortem s action items.

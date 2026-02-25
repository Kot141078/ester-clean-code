# ChatOps

## Teams (via Bastion/Runner)
- `/rollout status` → `chatops_rollouts.sh status`
- `/rollout abort` → `chatops_rollouts.sh abort`
- `/rollout promote` → `chatops_rollouts.sh promote`
- `/dr failover primary 100 secondary 0` → `failover_dns_weighted.sh`

Integratsiya s Telegram: webhook → GitHub Action/Runner → zapusk skripta s proverkoy podpisi i mappingom komand.

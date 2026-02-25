# G++ Guide

## Auto-rollback via Argo Rollouts
1. Vklyuchite v values: `rollouts.analysis.enabled=true`.
2. For canary/blue-green, the chart connects the AnalystSystemPlateyo and uses it in the strategy:
   - Canary: blok `analysis` vnutri `strategy.canary`.
   - Blue-Green: `prePromotionAnalysis` pered promoushenom.

## Adaptive SLO
If yorolluts.analysis.layer.adaptive.enabled=three, the heuristic pooleline n99 for the last yobaselineRange is used
(see comment in template). When in doubt, disable adaptive.

## Multi-cluster DR
- Yoskripts/mk_sync.she - synchronous deployment in eprimariyo and osekondariyo.
- eskripts/fileover_dns_veignted.she - switching the DNS weight (external-dns annotations for your provider).

## ChatOps
- yoskripts/chatops_rollouts.she - a wrapper over yokubetl argo rolloutsyo.
- Yoskripts/autorollbask_vach.she - external watcher on metrics for emergency abortion.

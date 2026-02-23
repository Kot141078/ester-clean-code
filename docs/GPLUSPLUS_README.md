# G++ Guide

## Auto-rollback cherez Argo Rollouts
1. Vklyuchite v values: `rollouts.analysis.enabled=true`.
2. Dlya canary/blue-green chart podklyuchaet `AnalysisTemplate` i ispolzuet ego v strategii:
   - Canary: blok `analysis` vnutri `strategy.canary`.
   - Blue-Green: `prePromotionAnalysis` pered promoushenom.

## Adaptive SLO
Esli `rollouts.analysis.slo.adaptive.enabled=true`, ispolzuetsya evristicheskiy baseline p99 za poslednie `baselineRange`
(sm. kommentariy v shablone). Pri somneniyakh otklyuchayte adaptiv.

## Multi-cluster DR
- `scripts/mc_sync.sh` — sinkhronnyy deploy v `primary` i `secondary`.
- `scripts/failover_dns_weighted.sh` — pereklyuchenie vesa DNS (external-dns annotatsii pod svoego provaydera).

## ChatOps
- `scripts/chatops_rollouts.sh` — obertka nad `kubectl argo rollouts`.
- `scripts/autorollback_watch.sh` — vneshniy votcher na metriki dlya avariynogo abort.

# Disaster Recovery Plan (DR)

**Tseli:** RPO ≤ 15 minut, RTO ≤ 30 minut.

## Urovni zaschity
1. **Bekapy:** obektnoe khranilische + lokalnyy snapshot. Ezhednevnyy `verify`.
2. **Multi-cluster:** aktivnyy primary, teplyy secondary (relizy sinkhronnye; trafik=0%).
3. **DNS-feylover:** pereklyuchenie vesa na secondary (cherez external-dns annotatsii).

## Drilly
- Ezhemesyachno: `restore_drill` na secondary iz poslednego bekapa.
- Ezhenedelno: chastichnyy feylover (10% trafika) na 30 minut — nablyudenie metrik.

## Chek-list avarii
1) Ostanovit relizy.
2) Otsenit masshtab.
3) Pri polnom otkaze — `failover_dns_weighted.sh` → weight=100 na secondary.
4) Kommunikatsiya (shablon intsidenta, status-kanaly).
5) Postmortem s action items.

# SLO Ester

## Dostupnost
- **Availability (HTTP success)**: ≥99.5% v mesyats (oshibka = 5xx).
- **Error budget**: 0.5%.

## Latentnost
- **p95** < 2s, **p99** < 5s for READ knobs (5-min window).

## Bekapy
- Last successful backup < 48x.

## Nablyudaemost
- Dashbord: LAT, ERR, RPS, BACKUP_AGE. Alerty: MWMB burn‑rate, p95/p99, backup stale.

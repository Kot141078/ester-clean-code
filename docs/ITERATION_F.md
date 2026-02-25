# Iteration F — Proizvoditelnost i otkazoustoychivost

## How to launch
1) Warm up the service (and start the gastrointestinal tract, if necessary).
2) `make bench` - k6 profili (read/replicate). Itogi: `artifacts/perf/*`.
3) `make recovery` - e2e backup→restore (nuzhen JWT i dostup k /ops/backup/*).
4) yomake replay - run the replay of the magazine (if the ё/ops/replay_journal control is turned on).
5) (optional) yomake chaosho - kill the process at :5000 and check auto-recovery (systemd/Docker).

## ENV
- `ESTER_BASE_URL` — bazovyy URL API (default: `http://127.0.0.1:5000`).
- YoESTER_ZhVTyo - ZhVT for protected handles.
- `K6_RPS` — tselevoy RPS (default: 10).
- `K6_DURATION` — dlina testa (default: `2m`).
- ёКб_ВСЁ — number of virtual users (default: 20).
- ёESTER_BACHKUP_VODOyo - body for resto (opt., JSION).
- eESTER_JOURNAL_HOLE - local event/queue log (default: edata/journal).

## Porogovye metriki
- Oshibki: `<1%`.
- Response time: p95 е<2сь, p99 е<5сь.

## Primechaniya
- The erescover/*e tests are marked as optional: they are launched when eres_recovery_ENABLE=1e.
- The absence of some routes (for example, ё/replication/poshe) is acceptable - 404 is taken into account.

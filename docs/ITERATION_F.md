# Iteration F — Proizvoditelnost i otkazoustoychivost

## Kak zapuskat
1) Progret servis (i zavesti JWT, esli nado).
2) `make bench` — k6 profili (read/replicate). Itogi: `artifacts/perf/*`.
3) `make recovery` — e2e backup→restore (nuzhen JWT i dostup k /ops/backup/*).
4) `make replay` — progon reigry zhurnala (esli vklyuchena ruchka `/ops/replay_journal`).
5) (opts.) `make chaos` — ubet protsess na :5000 i proverit avtopodem (systemd/Docker).

## ENV
- `ESTER_BASE_URL` — bazovyy URL API (default: `http://127.0.0.1:5000`).
- `ESTER_JWT` — JWT dlya zaschischennykh ruchek.
- `K6_RPS` — tselevoy RPS (default: 10).
- `K6_DURATION` — dlina testa (default: `2m`).
- `K6_VUS` — chislo virtualnykh polzovateley (default: 20).
- `ESTER_BACKUP_BODY` — telo dlya restore (opts., JSON).
- `ESTER_JOURNAL_DIR` — lokalnyy zhurnal sobytiy/ocheredey (default: `data/journal`).

## Porogovye metriki
- Oshibki: `<1%`.
- Vremya otklika: p95 `<2s`, p99 `<5s`.

## Primechaniya
- Testy `recovery/*` otmecheny kak optsionalnye: zapuskayutsya pri `ESTER_RECOVERY_ENABLE=1`.
- Otsutstvie nekotorykh routov (naprimer, `/replication/push`) dopustimo — 404 uchityvaetsya.

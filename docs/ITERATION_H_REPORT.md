# Iteration H — CRDT-pamyat i Merkle-sinkhronizatsiya

## Missiya
Garantirovat tselostnost i konsistentnost obschey BZ mezhdu uzlami bez konfliktov i poteri dannykh. Vstavleno drop-in: CRDT LWW-Set, Merkle-derevo dlya sverki, CAS (content-addressable), bezopasnyy P2P-protokol, avtosink i bekap.

---

## Definition of Done (DoD) — status

1. **CRDT sloy** — LWW-Element-Set:
   - Operatsii `add/remove`, metki `Dot(peer, ts)`.
   - Merge idempotenten, kommutativen, assotsiativen.
   - Testy: `tests/crdt/test_lww_set.py` — zelenye.

2. **Merkle sverka**:
   - Obmen kornem/urovnyami, `state(level, offset, limit)`.
   - Vetvevoy srez: `/p2p/state_branch?start&end`.
   - Klienty/diagnostika: `tools/p2p_verify_merkle.py`, `tools/p2p_diff_bisect.py`.
   - Benchmark: `tools/bench_merkle.py` (lokalno tsel `< 200ms` na 10k klyuchey, zavisit ot CPU).

3. **CAS**:
   - `merkle/cas.py` — `blake3` → fallback na `blake2b`.
   - Deduplikatsiya: `tests/merkle/test_cas_dedup.py`.

4. **P2P protokol**:
   - Ruchki: `/p2p/state`, `/p2p/state_branch`, `/p2p/pull`, `/p2p/push`, `/p2p/pull_by_ids`, `/p2p/snapshot/(export|import)`.
   - HMAC-podpis `X-HMAC-Signature`.
   - RBAC rol `replicator` pri `ESTER_RBAC_STRICT=1`.

5. **Avtosinkhronizatsiya**:
   - Planirovschik: `scheduler/sync_job.py` (`sync_once()` i loop).
   - systemd: `systemd/ester-p2p-sync.(service|timer)`.
   - UI/OPS: `/ops/p2p`, `/ops/p2p/diff`.

6. **Rezerv**:
   - Snapshot/import: `/p2p/snapshot/export|import`, `tools/p2p_snapshot.py`, vyborochnyy `tools/p2p_snapshot_select.py`.
   - systemd: `systemd/ester-crdt-snapshot.(service|timer)`.

---

## Zapusk

```bash
export ESTER_PEER_ID=peer-$(hostname)
export ESTER_P2P_HMAC="shared_secret"
export ESTER_P2P_STATIC="http://10.0.0.11:5000,http://10.0.0.12:5000"
export ESTER_RBAC_STRICT=1
export JWT_SECRET="change_me"

python app.py  # libo gunicorn 'app:create_app()'

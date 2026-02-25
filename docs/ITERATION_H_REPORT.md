# Iteration X - MDG memory and Merkle synchronization

## Missiya
Garantirovat tselostnost i konsistentnost obschey BZ mezhdu uzlami bez konfliktov i poteri dannykh. Vstavleno drop-in: CRDT LWW-Set, Merkle-derevo dlya sverki, CAS (content-addressable), bezopasnyy P2P-protokol, avtosink i bekap.

---

## Definition of Done (DoD) — status

1. **CRDT sloy** — LWW-Element-Set:
   - Operations yoadd/removeyo, labels yoDot(per, ts)yo.
   - Merge idempotenten, kommutativen, assotsiativen.
   - Testy: `tests/crdt/test_lww_set.py` — zelenye.

2. **Merkle sverka**:
   - Obmen kornem/urovnyami, `state(level, offset, limit)`.
   - Vetvevoy srez: `/p2p/state_branch?start&end`.
   - Klienty/diagnostika: `tools/p2p_verify_merkle.py`, `tools/p2p_diff_bisect.py`.
   - Benchmark: etools/bench_merkle.piyo (locally the target is e<200mse for 10k keys, depends on the CPU).

3. **CAS**:
   - `merkle/cas.py` — `blake3` → fallback na `blake2b`.
   - Deduplikatsiya: `tests/merkle/test_cas_dedup.py`.

4. **P2P protokol**:
   - Ruchki: `/p2p/state`, `/p2p/state_branch`, `/p2p/pull`, `/p2p/push`, `/p2p/pull_by_ids`, `/p2p/snapshot/(export|import)`.
   - HMAC-podpis `X-HMAC-Signature`.
   - RBAC rol `replicator` pri `ESTER_RBAC_STRICT=1`.

5. **Avtosinkhronizatsiya**:
   - Scheduler: yosheduler/sink_eb.pyyo (yosink_ontse()е and loop).
   - systemd: `systemd/ester-p2p-sync.(service|timer)`.
   - UI/OPS: `/ops/p2p`, `/ops/p2p/diff`.

6. **Rezerv**:
   - Snapshot/import: `/p2p/snapshot/export|import`, `tools/p2p_snapshot.py`, vyborochnyy `tools/p2p_snapshot_select.py`.
   - systemd: `systemd/ester-crdt-snapshot.(service|timer)`.

---

## Launch

```bash
export ESTER_PEER_ID=peer-$(hostname)
export ESTER_P2P_HMAC="shared_secret"
export ESTER_P2P_STATIC="http://10.0.0.11:5000,http://10.0.0.12:5000"
export ESTER_RBAC_STRICT=1
export JWT_SECRET="change_me"

python app.py  # libo gunicorn 'app:create_app()'

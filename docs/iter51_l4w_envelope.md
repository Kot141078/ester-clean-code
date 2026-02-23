# Iter51: L4 Witness Envelope v1

## Scope
- `drift.quarantine.clear` now supports L4W envelope (`ester.l4w.envelope.v1`) on top of evidence packet checks.
- Slot B enforces: envelope path/hash, signature, subject/evidence_ref match, and `prev_hash` chain continuity.
- Selective disclosure is supported via commitments in envelope + external disclosure packet.

## Envelope
- Schema: `ester.l4w.envelope.v1`
- Hash rule:
  - remove `sig`
  - remove `chain.envelope_hash`
  - canonicalize by RFC8785-safe subset: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)`
  - `sha256(...)` => `chain.envelope_hash`
- Signature: Ed25519 (`sig.alg=ed25519`, `sig.sig_b64`, `sig.pub_fingerprint`, `sig.key_id`).

## Selective Disclosure
- Envelope stores commitments only:
  - `claim.reviewer_commit.hash`
  - `claim.summary_commit.hash`
  - optional `claim.notes_commit.hash`
- Commitment formula:
  - `commit = sha256(salt_bytes || canonical_bytes(value))`
- Disclosure packet schema: `ester.l4w.disclosure.v1`
  - contains `envelope_hash` and `reveals[]` with `path`, `salt_b64`, `value`
  - signature is optional but supported.

## Chain Rules
- Ledger path: `PERSIST_DIR/l4w/chains/quarantine_clear/<agent_id>.jsonl`
- Genesis: `prev_hash == ""` when chain is empty.
- Non-genesis: `prev_hash == last_record.envelope_hash`.
- Slot B deny code on mismatch: `L4W_CHAIN_BROKEN`.

## Clear Validation Path
1. L4W path must be under `PERSIST_DIR/l4w/envelopes`.
2. Envelope file SHA256 must match provided `l4w.envelope_sha256`.
3. JSON/schema validation.
4. Signature + envelope hash verification.
5. Subject checks: `agent_id` and `quarantine_event_id`.
6. `evidence_ref.path` + `evidence_ref.sha256` must match already-validated evidence packet.
7. Chain continuity check.
8. Append chain ledger record after successful validation.

Persisted references:
- `quarantine_state.cleared` includes:
  - `l4w_envelope_path`
  - `l4w_envelope_sha256`
  - `l4w_envelope_hash`
  - `l4w_prev_hash`
  - `l4w_pub_fingerprint`
- Same fields are added to `QUARANTINE_CLEAR` event details and volition metadata.

## Runtime Status
- `/debug/runtime/status` adds top-level `l4w` block with:
  - slot/enforced/degraded
  - chain summary
  - `last_clear_l4w`

## A/B and Rollback
- Slot A: observe-only for L4W (`warnings`, no clear block).
- Slot B: enforce L4W (`L4W_REQUIRED`, `L4W_*` errors on failures).
- If Ed25519 unavailable in Slot B: failure is reported and failure streak can force Slot A.
- Optional compatibility switch: `ESTER_L4W_CHAIN_DISABLED=1` (status marks `chain_disabled`).

## Tools
- `python -B tools/l4w_build_envelope_for_clear.py --agent-id ... --event-id ... --evidence-path ... --evidence-sha256 ... --reviewer ... --summary ...`
- `python -B tools/l4w_verify_envelope.py --envelope-path ... --envelope-sha256 ...`
- `python -B tools/l4w_disclosure_make.py --envelope-path ...`
- `python -B tools/l4w_envelope_smoke.py`

## Bridges
- Explicit bridge (tamper-evident accountability): `prev_hash` chain plumbs every clear decision to the previous one, so rewriting one record breaks continuity.
- Hidden bridge #1 (information theory): selective disclosure transmits only needed bits (commitments + targeted reveals), not the full private context.
- Hidden bridge #2 (physiology): immune memory stores signatures/traces, then reconstructs detail on demand via disclosure.

## Earth Paragraph
Eto kak zhurnal dopuska na opasnyy uchastok: kazhdyy dopusk podpisan, svyazan s predyduschim nomerom, a chuvstvitelnye detali (kto chto skazal i pochemu) ne visyat na doske — vmesto etogo est kommitmenty, i pri proverke mozhno predyavit tolko nuzhnye stranitsy, ne raskryvaya vse ostalnoe.


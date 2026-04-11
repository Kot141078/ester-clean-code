# Iter52: L4W Conformance + Auditor CLI

## Profiles
| Profile | Required checks |
|---|---|
| `BASE` | Envelope file/hash/schema, signature verify, chain continuity, evidence path safety, evidence sha256/file (if `ESTER_L4W_AUDIT_REQUIRE_EVIDENCE_FILE=1`), subject match. |
| `HRO` | `BASE` + evidence packet signature + payload hash consistency + evidence subject fields + pubkey fingerprint alignment + disclosure verification when disclosure exists (or forced). |
| `FULL` | `HRO` + drift events/state cross-layer refs + volition journal linkage + strict replay/dup protections (`envelope_hash`, `envelope_id`, monotonic `ts`). |

Supported profiles: `BASE`, `HRO`, `FULL` (case-insensitive input, normalized to uppercase).

## Env knobs
- `ESTER_L4W_PROFILE_DEFAULT` (default `HRO`)
- `ESTER_L4W_AUDIT_MAX_RECORDS` (default `50`)
- `ESTER_L4W_AUDIT_REQUIRE_EVIDENCE_FILE` (default `1`)
- `ESTER_L4W_AUDIT_REQUIRE_DISCLOSURE` (default `0`)

## Auditor CLI
```powershell
python -B tools/auditor_verify_l4w.py --agent-id <id> --profile BASE --json
python -B tools/auditor_verify_l4w.py --agent-id <id> --profile HRO --max-records 100 --json
python -B tools/auditor_verify_l4w.py --agent-id <id> --profile FULL --persist-dir <repo-root>\data --json
```

Options:
- `--agent-id` required
- `--profile BASE|HRO|FULL`
- `--max-records N`
- `--check-disclosure`
- `--json`
- `--quiet`
- `--persist-dir PATH`

Exit codes:
- `0` pass
- `2` fail (errors present)
- `3` warnings-only (allowed only for `BASE`)

## Typical failure codes
- `ED25519_UNAVAILABLE`
- `L4W_HASH_MISMATCH`
- `L4W_SIG_INVALID`
- `L4W_PUBKEY_FINGERPRINT_MISMATCH`
- `L4W_CHAIN_BROKEN`
- `EVIDENCE_NOT_FOUND`
- `EVIDENCE_HASH_MISMATCH`
- `EVIDENCE_SIG_INVALID`
- `EVIDENCE_PAYLOAD_HASH_MISMATCH`
- `DRIFT_EVENT_REF_MISSING`
- `DRIFT_STATE_REF_MISMATCH`
- `VOLITION_JOURNAL_NOT_FOUND`
- `VOLITION_REF_MISSING`

## Runtime status
`/debug/runtime/status` now includes `l4w.conformance`:
- `supported`
- `default_profile`
- `last_audit_ts`
- `last_audit_profile`
- `last_audit_ok`
- `last_audit_error`

## Operational notes
- `FULL` is strict: if volition journal is expected but not discoverable under `PERSIST_DIR`, audit fails.
- Audit path safety is strict: auditor does not read artifacts outside `PERSIST_DIR`.
- Public proof publish mode: envelope-only is enough for base verification; disclosure packet is optional and can be provided selectively.

## Bridges
- Explicit bridge: `BASE/HRO/FULL` define conformance boundaries from integrity-only to full cross-layer traceability.
- Hidden bridge #1 (infotheory): selective disclosure + profile level tunes disclosure bandwidth to risk level.
- Hidden bridge #2 (anatomy/neuro): `BASE` is integrity reflex, `HRO` is contextual control, `FULL` is executive traceability through volition and system events.

## Earth paragraph
Eto kak tri rezhima proverki na proizvodstve: `BASE` - proverili plomby i nomera naryadov, `HRO` - podnyali akty laboratorii i sverili podpisi, `FULL` - sverili esche i zhurnal dopuska change: kto otkryl/kto zakryl, po kakomu osnovaniyu i s kakim artefaktom. Odna komanda auditora dolzhna umet skazat “da/net” bez ruchnogo detektiva.

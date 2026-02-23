# Iter49: Clear Requires Evidence Packet

## What And Why

`drift.quarantine.clear` is now an accountable action, not a trust-only override.
In Slot B, clear requires an evidence packet bound to a local file and its sha256.
Without valid evidence, clear is denied fail-closed.

This prevents silent/manual unblock without post-factum audit trail.

## Evidence Root

Evidence files must live under:

- `PERSIST_DIR/capability_drift/evidence`

Path safety rules:

- `evidence.path` can be relative or absolute.
- Final resolved path must stay inside `evidence_root`.
- Outside paths are rejected with `EVIDENCE_PATH_FORBIDDEN`.

## Evidence Packet v1

Required JSON fields:

- `schema`: `"ester.evidence.v1"`
- `created_ts`: `int`
- `reviewer`: `str`
- `agent_id`: `str`
- `quarantine_event_id`: `str`
- `decision`: `"CLEAR_QUARANTINE"`
- `summary`: `str` (short)

Optional:

- `findings`: `dict`
- `artifacts`: list of `{path, sha256, note}`
- `prev_hash`: `str`

## SHA256 Verification

Clear verification checks:

1. file exists
2. resolved path is inside `evidence_root`
3. `sha256(file_bytes)` equals provided `evidence.sha256`
4. JSON is valid and `schema == "ester.evidence.v1"`
5. packet `agent_id` matches clear `agent_id`
6. packet `quarantine_event_id` matches clear `event_id`
7. packet `decision == "CLEAR_QUARANTINE"`

## Slot Behavior

- Slot B:
  - evidence is mandatory
  - missing evidence -> `EVIDENCE_REQUIRED`
  - invalid evidence -> detailed `EVIDENCE_*` deny code
- Slot A:
  - evidence is warn-only
  - clear may continue with warning (`evidence_missing` / `evidence_invalid:*`)

Repeated evidence-check failures in Slot B contribute to quarantine fail-streak and can force Slot A in-process.

## Persisted Audit Fields

On clear, runtime stores evidence reference in:

- `quarantine_state.json` (`cleared.*`)
- `quarantine_events.jsonl` (`QUARANTINE_CLEAR.details`)
- volition journal metadata (`reason`, `evidence_ref`, `evidence_hash`)

Returned clear payload also includes:

- `evidence_path`
- `evidence_sha256`
- `evidence_schema`
- `evidence_created_ts`
- `reviewer`
- `evidence_summary`

## Example: Invoke Clear With Evidence

```python
from modules.thinking import action_registry

rep = action_registry.invoke_guarded(
    "drift.quarantine.clear",
    {
        "agent_id": "<agent_id>",
        "event_id": "<quarantine_event_id>",
        "reason": "manual audit completed",
        "by": "operator",
        "chain_id": "chain_clear_001",
        "evidence": {
            "path": "<agent_id>_<event_id>_<ts>.json",
            "sha256": "<64-lower-hex>",
        },
        "evidence_note": "ticket-42 review",
    },
)
```

## Bridges

Explicit bridge (audit / chain-of-custody):
clear is accountable only when tied to a concrete artifact and digest.

Hidden bridge #1 (information theory):
checksum is minimal integrity control linking decision to exact bytes.

Hidden bridge #2 (physiology):
quarantine release requires a lab protocol, not verbal confirmation.

## Earth Paragraph

Eto kak snyat plombu na schitovoy: nelzya prosto skazat “ya posmotrel, vse norm”.
Nuzhen akt proverki (evidence packet) s nomerom i kontrolnoy summoy.
Potom lyuboy audit sverit: chto imenno bylo provereno i na kakom osnovanii dali dostup obratno.


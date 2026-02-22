# Documentation Map

## Where To Start

- `QUICKSTART.md` - how to run basic checks locally.

- `L4W_ALIGNMENT.md` - what safety claims this repository makes (and does not).

- `ARCHITECTURE.md` - modules, boundaries, and where trust lives.

- `THREAT_MODEL.md` - practical failure modes and controls.

## Design Claims (Tight)

- Local-first by default; network is opt-in.

- Privileges must be explicit and auditable.

- Logs should be survivable and hash-friendly.

- Real constraints (L4) are treated as safety inputs.

## Non-Goals

- No autonomy promises.

- No containment guarantees.

- No hidden background operations.

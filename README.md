# Ester Clean Code

> **Ester is not a chatbot.**
> This repository publishes a clean-code core for accountable action under real constraints.

## What This Repository Is

- A public clean-code repository.
- A local-first operational core.
- A safety-oriented governance scaffold.
- A place where privileged actions are reviewable.

## What This Repository Is Not

- Not a generic conversation product.
- Not a promise of autonomy.
- Not a hidden-background-task framework.
- Not a storage for private runtime artifacts.

## Operational Process Premise

> “The future is not an event. It is a process.”
> — Ivan Kotov

Canonical note: see `Kot141078/advanced-global-intelligence` → `official/AUTHORIAL_PREMISES.md`

## Core Formula

- `c = a + b`
- `a` is a responsible human anchor.
- `b` is bounded policy plus executable controls.
- `c` is accountable behavior under constraints.

## Entity-centered runtime rule

- By default, `c` orchestrates agents; agents do not define `c`.
- Agents are bounded runtime processes and tools invoked under `c`.
- Continuity, privilege holding, and stopping authority remain at the `c` layer.
- Model replacement or worker rotation does not by itself redefine the entity.
- Canonical note: `docs/ENTITY_GOVERNS_AGENTS.md`

## L4 Reality Boundary

L4 treats real-world constraints as first-class safety input.

- time constraints
- access constraints
- spend constraints
- rate constraints
- irreversibility constraints

## Bridge Set

### Explicit Bridge

Every privileged action must map to:

- identity
- auditable privileges
- tamper-evident witness trail

### Hidden Bridge A (Ashby)

Control fails when regulator variety is lower than disturbance variety.

### Hidden Bridge B (Cover and Thomas)

Ambiguity reduces signal quality and coordination capacity.

### Earth Paragraph

Real systems degrade over time.
Fans fail.
Disks fill.
Clocks drift.
Keys leak.
Dependencies rot.

Ester therefore defaults to fail-closed behavior.
Uncertainty must degrade to safer outcomes.

## L4W Norms

This repository aligns with witness-first execution norms.

- identity is explicit
- privileges are explicit and least-privilege
- witness trail is durable and reviewable
- budgets are explicit (time, spend, rate)
- veto and challenge windows exist
- ambiguous state resolves to fail-closed behavior

## Operational Commitments

- deny-by-default for risky operations
- explicit escalation before irreversible action
- reviewable evidence packet for privileged changes
- deterministic local gates before push
- no background task assumptions in this release workflow
- policy and code drift treated as a release blocker
- challenge window for disputed actions
- safe stop when evidence is incomplete

## Repository Layout

- `ESTER/` contains runtime routes and surfaces.
- `modules/` contains subsystem implementations.
- `docs/` contains governance and operator docs.
- `docs/ENTITY_GOVERNS_AGENTS.md` defines the runtime entity / agent hierarchy.
- `tools/` contains local scanner and release helpers.

## Local Verification

Run compile checks:

```bash
python -m compileall ESTER
python -m compileall modules
```

Run scanner:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

## Opt-in Autonomy (Disabled By Default)

Auto initiative queueing and self-evo hooks are disabled by default.
They activate only with explicit operator opt-in and fail-closed prerequisites.

### Required Flags

- `ESTER_ENABLE_AUTO_TASKS=1` for initiative queue generation
- `ESTER_ENABLE_SELF_EVO=1` for self-evo forge entrypoints
- `ESTER_ACK_AUTONOMY_RISK=I_UNDERSTAND` for explicit risk acknowledgement
- `ESTER_L4W_WITNESS=1` (or runtime witness-ready signal)

### Quick Enable (Operator Example)

```bash
export ESTER_ENABLE_AUTO_TASKS=1
export ESTER_ENABLE_SELF_EVO=1
export ESTER_ACK_AUTONOMY_RISK=I_UNDERSTAND
export ESTER_L4W_WITNESS=1
export ESTER_AUTO_TASKS_MAX_ITEMS=5
export ESTER_AUTO_TASKS_WINDOW=60
export ESTER_AUTO_TASKS_MAX_WORK_MS=2000
```

### Fail-Closed Status Examples

Disabled by default:

```json
{"ok": true, "enabled": false, "reason": "disabled_by_default", "created": []}
```

Enabled but missing prerequisites:

```json
{"ok": true, "enabled": false, "reason": "missing_prereqs", "missing": ["ACK", "WITNESS", "BUDGETS"]}
```

See `docs/SELF_EVO_OPTIN.md` for full prerequisites, controls, and operator checklist.

## Security and Rights

- Security policy: `SECURITY.md`
- Code license: AGPL-3.0-or-later (`LICENSE`)
- Trademark separation: `TRADEMARK.md`
- Notices: `NOTICE`

## Related Public Corpus

- AGI v1.1: https://github.com/Kot141078/advanced-global-intelligence/releases/tag/v1.1
- ester-reality-bound: https://github.com/Kot141078/ester-reality-bound
- sovereign-entity-recursion: https://github.com/Kot141078/sovereign-entity-recursion
- Theoretical Foundations of the AGI Ecosystem: https://github.com/Kot141078/advanced-global-intelligence/blob/main/manifesto/Theoretical_Foundations_of_the_AGI_Ecosystem_EN.md

---

## Machine entry / downloads (no UI)
- Machine entry (raw):
  https://raw.githubusercontent.com/Kot141078/ester-clean-code/main/MACHINE_ENTRY.md
- llms.txt (raw):
  https://raw.githubusercontent.com/Kot141078/ester-clean-code/main/llms.txt
- Tag snapshot ZIP:
  https://github.com/Kot141078/ester-clean-code/archive/refs/tags/v0.2.3.zip
- Verify content via `hashes/` and local tools (do not hash GitHub-generated archives).

## Glitch Stack — implementation bridge v0.1

This repository now hosts the **implementation-facing** side of the glitch-stack package set.

Primary entry:
- [`docs/architecture/glitch-stack/INDEX.md`](docs/architecture/glitch-stack/INDEX.md)

Subtrees:
- [`docs/architecture/glitch-stack/implementation/`](docs/architecture/glitch-stack/implementation/)
- [`docs/architecture/glitch-stack/milestone-m1/`](docs/architecture/glitch-stack/milestone-m1/)

This subtree is intentionally code-facing:
bridge, anatomy, validators, reducers, events, tests, and Milestone M1.

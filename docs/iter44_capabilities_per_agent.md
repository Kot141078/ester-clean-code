# Iter44: Capabilities Per Agent

## What Changed

- Agent authority is now capability-based.
- `allowed_actions` are derived from template capabilities (or legacy template defaults when capabilities are absent).
- Plan payloads cannot expand privileges.
- Enforcement is now duplicated:
  - early deny on enqueue (`agent.queue.enqueue`)
  - runtime deny in runner (`agent.run.step`)

## Capability Model

- Source of truth: `modules/garage/templates/registry.py`
  - `CAPABILITY_ACTIONS`
  - `resolve_allowed_actions(capabilities, registry)`
- Requirements:
  - unknown capability => deny
  - unknown action mapping => deny
  - deterministic allowlist (deduped + sorted)

## Authority Flow

- Template path:
  - if template has capabilities: capabilities => allowlist
  - if template has no capabilities: legacy `default_allowed_actions` path (template-authoritative only)
- Overrides:
  - capabilities override must be subset of template capabilities
  - Slot A: clamp + warnings
  - Slot B: deny escalation
- Create:
  - persisted in agent spec/index:
    - `template_id`
    - `capabilities_effective`
    - `allowed_actions_hash`
    - `capabilities_hash`

## Enforcement Points

- `agent.queue.enqueue`:
  - loads AgentSpec authority
  - validates all plan step actions are in allowlist
  - deny response includes `error_code=ACTION_NOT_ALLOWED` and `disallowed_actions`
  - writes explicit deny/allow row into volition journal
- `agent_runner.run_once`:
  - fail-closed when allowlist invalid/empty in Slot B
  - deny and stop on first disallowed step
  - writes deny row with `step="agent.run.step"`

## Verification Commands

- `python -B tools/agent_capabilities_smoke.py`
- `python -B tools/agent_queue_smoke.py`
- `python -B tools/agent_supervisor_smoke.py`
- `powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet`

## Bridges

Explicit bridge (security engineering): least-privilege capability model, where templates define authority and plans only consume authority.

Hidden bridge #1 (information theory): capabilities form a bounded control channel; plan data cannot increase control capacity.

Hidden bridge #2 (physiology): planning and execution are distinct; execution still needs enabling circuits, here represented by capabilities plus journaled policy checks.

## Earth Paragraph

Factory badge model: agent badge (capabilities) defines where the agent can go. Work order (plan) cannot add new doors. Security blocks on entry (enqueue deny), and shop-floor control blocks again at machine execution (runner deny).


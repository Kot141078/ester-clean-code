# Iter43: Plan Schema Hardening v1

## `ester.plan.v1`

Canonical plan payload:

- Required:
  - `schema: "ester.plan.v1"`
  - `plan_id: str`
  - `steps: list[step]`
- Optional:
  - `created_ts: int`
  - `title: str`
  - `intent: str`
  - `initiative_id: str`
  - `agent_id: str`
  - `template_id: str`
  - `budgets: {max_ms:int, max_steps:int, window_sec:int, oracle_window?:str}`
  - `meta: dict` (JSON-safe, depth/size limited)

Step schema:

- Required:
  - `action: str` (legacy `action_id` accepted only at normalize stage)
- Optional:
  - `args: dict` (default `{}`)
  - `why: str` (default `agent_step:<action>`)
- Forbidden:
  - any extra keys (for example `do`, `exec`, `python`, `code`, `pwn`, and any unknown field)

Hard limits:

- steps count <= 64 (and <= `budgets.max_steps` when provided)
- `action` length <= 120
- `why` length <= 500
- `args` JSON size <= 32KB
- `args` depth <= 8

## Validation Flow

- Normalize: `modules/agents/plan_schema.py::normalize_plan`
  - converts legacy `action_id -> action`
  - applies defaults (`why`, `plan_id`)
- Validate: `modules/agents/plan_schema.py::validate_plan`
  - strict shape/type checks
  - unknown action deny via `modules/thinking/action_registry.py::has_action`
- Path loading: `load_plan_from_path`
  - `.json` via `json`
  - `.yaml/.yml` via `yaml.safe_load` only if PyYAML exists
  - otherwise: `yaml_not_supported_no_deps`

## Slot Behavior + Auto-Rollback

- Slot A:
  - lenient mode with normalization and warnings
  - compatibility-first path for legacy plans
- Slot B:
  - strict fail-closed validation in queue and runner
  - unknown actions and unknown step keys are denied before execution
- Auto-rollback:
  - strict runtime exceptions are counted in-process
  - after configured threshold (`ESTER_PLAN_SCHEMA_STRICT_FAIL_MAX`), strict path is disabled in-process and fallback switches to Slot A behavior with rollback reason in env/status

## Bridges

Explicit bridge (Enderton, logic): plan schema is a formal language, and validation is type-checking before execution, so the agent is not an interpreter of arbitrary strings.

Hidden bridge #1 (Cover & Thomas, information theory): the allowed `action_id` list is a codebook; an unknown symbol must fail decoding, otherwise it becomes an injection channel.

Hidden bridge #2 (Gray’s anatomy / physiology): motor control runs known motor programs; the spinal system does not execute arbitrary text. The agent should execute only known actions.

## Earth Paragraph

This is like a PLC on a factory line: the controller executes only known opcodes. If an unknown opcode appears, the machine stops and waits for a human instead of guessing. Without that rule, one broken plan can turn production into fireworks.


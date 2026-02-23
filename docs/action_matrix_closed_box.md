# Action Matrix Closed Box (Iter29)

This matrix is the source of truth for Agent OS v1 in offline-first mode.

## Rules
- Default policy is deny outbound network.
- Every initiative -> plan -> agent -> action step must pass Volition Gate.
- `requires_oracle=true` actions are allowed only in Slot B and only with an open oracle window.
- Budgets are mandatory for every action (`max_actions`, `max_work_ms`, `window`, optional `est_work_ms`).

## Actions

| action_id | category | required_scopes | risk_level | default_budget | requires_oracle | notes |
|---|---|---|---|---|---|---|
| `memory.add_note` | memory | `memory:write` | low | `{"max_actions":1,"max_work_ms":500,"window":60}` | false | Local memory note write; fallback file allowed if facade is read-only. |
| `initiative.mark_done` | proactivity | `initiative:write` | low | `{"max_actions":1,"max_work_ms":400,"window":60}` | false | Marks initiative as processed in local state. |
| `proactivity.queue.add` | proactivity | `initiative:write` | low | `{"max_actions":1,"max_work_ms":400,"window":60}` | false | Enqueues synthetic/local initiative item. |
| `files.sandbox_write` | filesystem | `files:write_sandbox` | medium | `{"max_actions":1,"max_work_ms":1200,"window":60}` | false | Write is restricted to `data/garage/agents/<id>/sandbox` only. |
| `files.sha256_verify` | filesystem | `files:read_sandbox` | low | `{"max_actions":1,"max_work_ms":600,"window":60}` | false | Computes SHA-256 for a sandbox-relative file path. |
| `oracle.openai.call` | oracle | `oracle:remote_llm` | high | `{"max_actions":1,"max_work_ms":3000,"window":60}` | true | Needs Slot B, oracle window, host allowlist and Volition allow. |

## Earth paragraph
This works like an electrical panel: each action has a rated breaker (budget), and Volition Gate is the safety relay. Oracle window is a temporary external socket with timer and reason, not a permanent outbound wire.


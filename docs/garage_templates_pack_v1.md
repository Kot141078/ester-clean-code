# Garage Templates Pack v1

Iter31 adds a safe template pack for rapid Garage agent creation without enabling outbound network by default.

| template_id | purpose | allowed_actions (stable IDs) | default budgets | notes |
| --- | --- | --- | --- | --- |
| `archivist.v1` | local archive summary | `fs.list`, `fs.read`, `memory.ingest`, `memory.add_note`, `messages.outbox.enqueue` | `max_steps=6`, `max_work_ms=3000`, `window_sec=60` | partial mode allowed when optional actions are unavailable |
| `dreamer.v1` | one dream cycle | `dreams.run_once`, `messages.outbox.enqueue` | `max_steps=4`, `max_work_ms=2500`, `window_sec=60` | offline-first |
| `initiator.v1` | queue initiative | `initiatives.run_once`, `proactivity.queue.add`, `initiative.mark_done`, `messages.outbox.enqueue` | `max_steps=5`, `max_work_ms=3000`, `window_sec=60` | safe queue/update path |
| `planner.v1` | draft plan file | `plan.build`, `fs.write`, `messages.outbox.enqueue` | `max_steps=5`, `max_work_ms=3000`, `window_sec=60` | writes only to sandbox root |
| `builder.v1` | write/patch/hash artifact | `fs.write`, `fs.patch`, `fs.hash`, `messages.outbox.enqueue` | `max_steps=6`, `max_work_ms=3500`, `window_sec=60` | SHA256 verification auto-derived from write step |
| `reviewer.v1` | checks summary | `run_checks_offline`, `route_registry_check`, `route_return_lint`, `messages.outbox.enqueue` | `max_steps=5`, `max_work_ms=3000`, `window_sec=60` | falls back safely if wrappers are unavailable |
| `runner.v1` | nested safe run | `agent.run_once`, `messages.outbox.enqueue` | `max_steps=4`, `max_work_ms=2500`, `window_sec=60` | no network by default |
| `oracle.v1` | remote LLM (strict OFF by default) | `llm.remote.call`, `messages.outbox.enqueue` | `max_steps=3`, `max_work_ms=2500`, `window_sec=60` | requires opened oracle window + Volition allow |

## Alias strategy

Templates use stable action IDs. Registry translates them to project action IDs via alias table.  
If an optional action does not exist in runtime, template becomes partially available and inserts safe fallback steps.

## Policy defaults

- OFFLINE-FIRST by default (`oracle` and `comm` disabled).
- Every template defines `allowed_actions`, `budgets`, and `scopes`.
- Any execution still goes through Action Registry + Volition Gate.

## Bridges

- Explicit bridge (Ashby cybernetics): templates increase regulator variety while staying bounded by Action Matrix and Volition Gate.
- Hidden bridge #1 (Enderton logic): template is a typed contract with predefined admissible action domain (`allowed_actions`).
- Hidden bridge #2 (Cover & Thomas information theory): budgets and bounded plans cap channel capacity, so the agent cannot flood execution with unbounded steps.

## Earth paragraph

Templates Pask is like a set of proven attachments for a drill: you don’t have to sharpen the chuck by hand every time.
But electricity (oracle/comm) is turned off by default: to turn on the “network”, you need to open the window and write down the reason - like a key to a dashboard.
This is how the agent “garage” grows, but Esther does not lose face: the Companion remains the voice, and the agents remain the hands.


# Iter59: Curiosity v3 (Unknown Ticket Pipeline)

## Null vs Zero
- `NULL` is represented as an explicit `UnknownTicket` (open/planned/enqueued/resolved lifecycle).
- `0` is represented as `crystallize.negative` (we searched with budget and found no reliable support).
- This prevents silent loss of unknowns and separates "not yet known" from "known absence".

## Flow
1. Detect: dialog/dream paths call `maybe_open_ticket(...)` for `pending`, `memory_miss`, `low_confidence`.
2. Ticket: append-only event log in `data/curiosity/tickets.jsonl` + aggregate `data/curiosity/state.json`.
3. Plan: `curiosity_planner.build_plan(...)` builds strict `ester.plan.v1` with allowlisted actions.
4. Enqueue: `executor.run_once(...)` performs volition-gated ticket->plan->agent->queue chain.
5. Execute in window: only supervisor executes when `execution_window` is open.
6. Crystallize: `crystallize.fact` / `crystallize.negative` writes memory only with `evidence_ref + L4W`.
7. Close: ticket gets `resolve/negative/fail/stale` event with references.

## Budgets and Anti Rabbit-Hole
- Budgets: `max_depth`, `max_hops`, `max_docs`, `max_work_ms`.
- Dedupe: `plan_hash` + cooldown to avoid repeated enqueues.
- Queue guard: `max_queue_size` blocks overload.
- Slot fallback: repeated Slot B runtime errors auto-fallback to Slot A in-process.

## Tools
- `python -B tools/curiosity_tick_once.py --plan-only --json`
- `python -B tools/curiosity_tick_once.py --enqueue --json`
- `python -B tools/curiosity_e2e_smoke.py`
- `python -B tools/no_network_guard.py --quiet`
- `python -B tools/no_network_guard.py --strict`

## No-Network Guard
- Static scan for network-risk imports/usages (`requests`, `httpx`, `aiohttp`, `websockets`, `urllib.request`, `socket.create_connection`).
- Allowlist is explicit: `config/no_network_allowlist.json`.
- In offline checks:
  - WARN mode always runs.
  - STRICT mode runs only when `ESTER_NO_NET_GUARD_STRICT=1`.

## Bridge (Ashby, Cybernetics)
Curiosity becomes controllable only when the unknown is transformed into an observable object (ticket) with constrained budgets.

## Hidden Bridge #1 (Cover & Thomas, Information Theory)
`dedupe/cooldown/max_depth` are channel-capacity controls; without them, unknowns degrade into infinite search noise.

## Hidden Bridge #2 (Dhammapada, Discipline of Attention)
"Do not follow every thought" maps to planned, permit-based execution with explicit limits to avoid rabbit-hole drift.

## Earth Paragraph
Eto kak dispetcherskaya: neizvestnoe - eto ne "pustota", a zayavka. Zayavku registriruyut, planiruyut, kladut v ochered, i tolko po podpisannomu dopusku vklyuchayut stanok (`execution_window`). A rezultat prinimayut po aktu (`evidence + L4W`), inache eto ne znanie, a boltovnya.

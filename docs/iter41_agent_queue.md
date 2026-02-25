# Iter41 Agent Queue

## What has been done

- Added `modules/garage/agent_queue.py`: append-only ochered planov v `data/agents/queue.jsonl`, `fold_state()`, `select_next()`, perekhody `enqueue/claim/start/done/fail/cancel/expire`.
- Add `modules/runtime/execution_window.py`: okno ispolneniya po umolchaniyu zakryto, `open_window/close_window/current_window/status`, zhurnal `data/windows/execution_window.jsonl`.
- Add `modules/garage/agent_supervisor.py`: `tick_once(actor, reason, dry_run)` s proverkoy execution window, challenge window, zapuskom `agent_runner.run_once`, i zhurnalirovaniem resheniy v `modules.volition.journal`.
- Extended emodules/thinking/action_registers.piyo with actions:
  - `agent.queue.enqueue`
  - `agent.queue.list`
  - `agent.queue.cancel`
  - `agent.supervisor.tick_once`
  - `execution_window.open`
  - `execution_window.close`
  - `execution_window.status`
- Dobavleny smoke:
  - `tools/agent_queue_smoke.py`
  - `tools/agent_supervisor_smoke.py`
  - `tools/execution_window_smoke.py`
- Updated yotools/run_chess_offline.ps1yo: new smoke steps (if files are present), while maintaining the behavior of yo-Kito.

## Invarianty

- Default-safe: if the Windows essotion is closed/expired, agent_superhigh.tisk_onsay does nothing.
- Challenge Windows: yoselect_next() selects only yoenqueuedo tasks from yon >= not_before_tso.
- One tick = one launch attempt; If there is an error, the error is fixed, there is no endless retro.
- Resheniya supervisor pishutsya v volition journal s `policy_hit` (`supervisor_tick`, `queue_claim`, `queue_blocked_window`, `queue_blocked_challenge`, `queue_start`).

## Teams

```powershell
python -B tools/agent_queue_smoke.py
python -B tools/agent_supervisor_smoke.py
python -B tools/execution_window_smoke.py
powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet
```

## Bridges

- Yavnyy most: dispetcherizatsiya deystviy = otvetstvennost subekta (Ester), a ne pravo agenta; supervisor prinimaet reshenie tolko pri validnom `actor=ester*` i otkrytom execution window.
- Hidden bridge #1 (cybernetics, Ashby): queue + esesotion windows limit the gain of the circuit and dampen self-excitation (damper before starting actions).
- Hidden bridge #2 (infotheory/bayes): yonut_before_tsyo reduces false positives by adding time to update signals before execution.

## Earth Paragraph

This is how prefrontalnaya kora protiv refleksa: myshtsa mozhet dernutsya srazu, no razreshenie dvizheniya daet upravlyayuschiy kontur s zaderzhkoy i kontekstom. V inzhenerii eto relay + debounce: bez okna i zaderzhki poluchaetsya drebezg, a ne deystvie. `queue + execution window + journal` prevraschayut impuls v kontroliruemyy akt s nablyudaemoy prichinoy.

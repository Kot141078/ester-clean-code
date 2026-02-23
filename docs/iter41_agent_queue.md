# Iter41 Agent Queue

## Chto sdelano

- Dobavlen `modules/garage/agent_queue.py`: append-only ochered planov v `data/agents/queue.jsonl`, `fold_state()`, `select_next()`, perekhody `enqueue/claim/start/done/fail/cancel/expire`.
- Dobavlen `modules/runtime/execution_window.py`: okno ispolneniya po umolchaniyu zakryto, `open_window/close_window/current_window/status`, zhurnal `data/windows/execution_window.jsonl`.
- Dobavlen `modules/garage/agent_supervisor.py`: `tick_once(actor, reason, dry_run)` s proverkoy execution window, challenge window, zapuskom `agent_runner.run_once`, i zhurnalirovaniem resheniy v `modules.volition.journal`.
- Rasshiren `modules/thinking/action_registry.py` deystviyami:
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
- Obnovlen `tools/run_checks_offline.ps1`: novye smoke shagi (esli fayly prisutstvuyut), s sokhraneniem povedeniya `-Quiet`.

## Invarianty

- Default-safe: esli execution window zakryto/isteklo, `agent_supervisor.tick_once` nichego ne ispolnyaet.
- Challenge window: `select_next()` vybiraet tolko `enqueued` zadachi s `now >= not_before_ts`.
- Odin tick = odna popytka zapuska; pri oshibke fiksiruetsya `fail`, beskonechnyy retry otsutstvuet.
- Resheniya supervisor pishutsya v volition journal s `policy_hit` (`supervisor_tick`, `queue_claim`, `queue_blocked_window`, `queue_blocked_challenge`, `queue_start`).

## Komandy

```powershell
python -B tools/agent_queue_smoke.py
python -B tools/agent_supervisor_smoke.py
python -B tools/execution_window_smoke.py
powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet
```

## Bridges

- Yavnyy most: dispetcherizatsiya deystviy = otvetstvennost subekta (Ester), a ne pravo agenta; supervisor prinimaet reshenie tolko pri validnom `actor=ester*` i otkrytom execution window.
- Skrytyy most #1 (kibernetika, Ashby): ochered + execution window ogranichivayut usilenie kontura i gasyat samovozbuzhdenie (dempfer pered zapuskom deystviy).
- Skrytyy most #2 (infoteoriya/bayes): `not_before_ts` snizhaet lozhnye srabatyvaniya, dobavlyaya vremya na obnovlenie signalov do ispolneniya.

## Earth Paragraph

Eto kak prefrontalnaya kora protiv refleksa: myshtsa mozhet dernutsya srazu, no razreshenie dvizheniya daet upravlyayuschiy kontur s zaderzhkoy i kontekstom. V inzhenerii eto relay + debounce: bez okna i zaderzhki poluchaetsya drebezg, a ne deystvie. `queue + execution window + journal` prevraschayut impuls v kontroliruemyy akt s nablyudaemoy prichinoy.

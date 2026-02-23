# Iter42 Proactivity Enqueue

## Chto izmeneno

- `modules/proactivity/executor.py`
  - `run_once(..., mode=\"enqueue\"|\"plan_only\")` s backward-compatible vyzovom po `dry`.
  - Payplayn: `initiative -> planner_v1 -> template_bridge -> agent.create/reuse -> agent.queue.enqueue`.
  - Ispolnenie plana otklyucheno: net `agent_runner.run_once`, net `supervisor.tick_once`.
  - Guard'y: `max_work_ms`, `max_queue_size`, `cooldown_sec` po `plan_hash`.
  - Slot A prinuditelno `plan_only`; Slot B razreshaet `enqueue`; pri serii oshibok Slot B -> in-process rollback v `plan_only`.
  - Dobavlen append-only log: `data/proactivity/enqueue.jsonl`.

- `tools/proactivity_tick_once.py`
  - Pereveden na rezhim enqueue-only CLI poverkh `executor.run_once`.
  - Flagi: `--plan-only`, `--enqueue`, `--max-work-ms`, `--max-queue-size`, `--cooldown-sec`, `--dry-run`.

- `tools/proactivity_enqueue_smoke.py`
  - Proveryaet zakrytoe execution window.
  - Proveryaet, chto proactivity v rezhime enqueue uvelichivaet razmer ocheredi.
  - Proveryaet otsutstvie execution-sobytiy (`claim/start/done/fail`) i otsutstvie run-zapisey.
  - Proveryaet volition steps: `proactivity.plan`, `agent.create`, `agent.queue.enqueue`.

- `modules/runtime/status_iter18.py`
  - V `proactivity` dobavleny: `last_plan_ts`, `last_enqueue_ts`.
  - Dobavlen blok `queue`: `size`, `last_enqueue_id`.

- `tools/run_checks_offline.ps1`
  - Dobavlen shag `proactivity_enqueue_smoke` (s uvazheniem `-Quiet`).

## Komandy

```powershell
python -B tools/proactivity_tick_once.py --enqueue
python -B tools/proactivity_enqueue_smoke.py
powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet
```

## Bridges

- Yavnyy most (Ashby): nablyudaemaya dispetcherizatsiya otdelena ot ispolneniya. Proactivity tolko proizvodit zadachi (`enqueue`), ispolnenie ostaetsya za `supervisor + execution_window`.
- Skrytyy most #1 (infoteoriya): ogranichenie propusknoy sposobnosti cherez `max_queue_size` i `cooldown_sec` podavlyaet shum i povtornye lozhnye impulsy.
- Skrytyy most #2 (fiziologiya): kak prefrontalka i bazalnye ganglii: snachala plan i otbor, deystvie tolko pri otdelnom razreshenii okna ispolneniya.

## Earth Paragraph

Ochered + okno ispolneniya — eto kak dispetcherskaya i naryad-dopusk na zavode: zayavki mozhno prinyat i razlozhit po lotkam (`enqueue`), no stanok ne vklyuchat bez podpisannogo dopuska (`execution_window`). Eto zaschischaet ot samozapuska: dazhe esli nochyu sgenerirovano mnogo planov, oni ne ispolnyatsya bez yavnogo otkrytiya okna i vydelennogo byudzheta.

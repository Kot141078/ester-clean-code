# Iter42 Proactivity Enqueue

## What's changed

- `modules/proactivity/executor.py`
  - `run_once(..., mode=\"enqueue\"|\"plan_only\")` s backward-compatible vyzovom po `dry`.
  - Payplayn: `initiative -> planner_v1 -> template_bridge -> agent.create/reuse -> agent.queue.enqueue`.
  - Plan execution is disabled: no yoagent_runner.run_onsey, no yosuperhigh.tisk_onsey.
  - Guard'y: `max_work_ms`, `max_queue_size`, `cooldown_sec` po `plan_hash`.
  - Slot A forced eplan_onlyo; Slot B allows yenkuyee; in case of a series of errors Slot B -> in-process rollback in eplan_onlyo.
  - Dobavlen append-only log: `data/proactivity/enqueue.jsonl`.

- `tools/proactivity_tick_once.py`
  - Switched to engueue-only CLI mode over yeesekutor.run_onseyo.
  - Flagi: `--plan-only`, `--enqueue`, `--max-work-ms`, `--max-queue-size`, `--cooldown-sec`, `--dry-run`.

- `tools/proactivity_enqueue_smoke.py`
  - Checks the closed essotion of Windows.
  - Checks that proactivites in engueue mode increase the queue size.
  - Checks for the absence of essotion events (yoklaym/start/done/file) and the absence of rune records.
  - Proveryaet volition steps: `proactivity.plan`, `agent.create`, `agent.queue.enqueue`.

- `modules/runtime/status_iter18.py`
  - V `proactivity` dobavleny: `last_plan_ts`, `last_enqueue_ts`.
  - Dobavlen blok `queue`: `size`, `last_enqueue_id`.

- `tools/run_checks_offline.ps1`
  - Added step yoproactivity_engueue_smokeyo (respectfully yo-Kicho).

## Teams

```powershell
python -B tools/proactivity_tick_once.py --enqueue
python -B tools/proactivity_enqueue_smoke.py
powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet
```

## Bridges

- Yavnyy most (Ashby): nablyudaemaya dispetcherizatsiya otdelena ot ispolneniya. Proactivity tolko proizvodit zadachi (`enqueue`), ispolnenie ostaetsya za `supervisor + execution_window`.
- Hidden Bridge #1 (infotheory): limiting the capacity through yomah_kuueue_sizeyo and yokooldovn_syosyo suppresses noise and repeated false pulses.
- Hidden Bridge #2 (Physiology): Like the prefrontal and basal ganglia: plan and select first, act only on separate execution window resolution.

## Earth Paragraph

Ochered + okno ispolneniya - eto kak dispetcherskaya i naryad-dopusk na zavode: zayavki mozhno prinyat i razlozhit po lotkam (`enqueue`), no stanok ne vklyuchat bez podpisannogo dopuska (`execution_window`). Eto zaschischaet ot samozapuska: dazhe esli nochyu sgenerirovano mnogo planov, oni ne ispolnyatsya bez yavnogo otkrytiya okna i vydelennogo byudzheta.

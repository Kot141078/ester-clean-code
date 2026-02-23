# Iter36 Stub Zero

## Targets (source: data/reports/stubs_kill_list.jsonl before fixes)

| # | path:symbol | kind | why stub | implemented |
|---:|---|---|---|---|
| 1 | modules/mm/guard.py:__module__ | suppress_init | import-time `try/except: pass` around `patch_get_mm()` silently hid init errors | Added `bootstrap_patch()` with tracked status (`_BOOTSTRAP`), explicit bypass flagging on failures, and import-time deterministic bootstrap call. |
| 2 | modules/context/telegram_adapter.py:start_background | pass_only | disabled duplicate adapter had empty background entrypoint | Implemented explicit disabled-adapter response (`ok/started/reason_code/how_to_enable`) and reused `listen()` for consistent operator signal. |
| 3 | modules/thinking/actions_social.py:_p2p_sync | pass_only | local P2P sync hook existed but was empty | Implemented bounded offline queue writer to `data/social/p2p_sync_queue.jsonl` (no network calls, deterministic payload). |
| 4 | modules/utils/ipc_lock.py:LockError | pass_only | exception type existed without semantics | Replaced body with clear docstring contract for lock-acquisition failures. |
| 5 | modules/web_log.py:WebLogError | pass_only | base exception existed without semantics | Replaced body with clear docstring contract for web logging/budget failures. |

## Gate Tightening (ratchet)

- `tools/stubs_gate.py`:
  - Added `--ratchet 1` mode.
  - If baseline exists and current total is lower, baseline is updated to current summary.
  - Added output fields: `baseline_updated`, `baseline_old_total`, `baseline_new_total`.
  - Kept fail behavior for reachable stubs and increases.
  - Baseline write is atomic-first (`temp + replace`) with controlled fallback for restrictive Windows ACLs.
- `tools/run_checks_offline.ps1` updated to pass `--ratchet 1` in stubs gate step.

## Mojibake Tightening

- `tools/mojibake_doctor.py` heuristics tightened for UTF8->CP1251 patterns.
- Added odd-pair checks and known tokens (`RґRЅRµR№`, `RџSЂ`) while avoiding normal Cyrillic over-flagging.
- Iter36 scan performed only on touched files.

## Commands and Short Outputs

```powershell
python -B tools/stubs_kill_list.py --root modules --entry run_ester_fixed.py --out-md docs/stubs_kill_list.md --out-jsonl data/reports/stubs_kill_list.jsonl --top 500
# before fixes: total_stubs=5, reachable_stubs=0
# after fixes:  total_stubs=0, reachable_stubs=0

python -B tools/stubs_gate.py --jsonl data/reports/stubs_kill_list.jsonl --baseline docs/stubs_baseline.json --allowlist docs/stubs_allowlist.json --fail-on-reachable 1 --fail-on-increase 1 --ratchet 1 --quiet 1
# ok=true, baseline_updated=true, baseline_old_total=5, baseline_new_total=0, baseline_total_stubs=0

powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet
# PASS

python -B tools/mojibake_doctor.py --scan --paths "<touched_files>"
# ok=true, findings=0
```

## Bridges

- Explicit bridge (Ashby): ratchet delaet `stubs_gate` realnym regulyatorom, regress v stubs ne prokhodit tikho.
- Hidden bridge #1 (Cover&Thomas): zakryvaem poslednie 5 stubs vmesto rasshireniya funktsionalnosti, snizhaya entropiyu izmeneniy.
- Hidden bridge #2 (Guyton/Hall): `stubs=0` fiksiruet gomeostaz koda; posle etogo mozhno bezopasno naraschivat agentnye sloi.

## Earth Paragraph

Eto kak elektrika v kvartire: poka v stene ostavalis 5 «skrutok izolentoy», sistema rabotala na udache. My ne tolko zamenili skrutki na klemmy, no i postavili avtomat (`ratchet gate`), chtoby novye «skrutki na soplyakh» bolshe ne prokhodili kommitom.

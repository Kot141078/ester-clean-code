# Stubs Kill List

## Summary
- total_stubs: 0
- reachable_stubs: 0
- app_py_entrypoints: 0
- top_stub_kinds: {}

## Top-30

| rank | severity | reachable | path:symbol | stub_kind | reach_reason | refs | suggested_fix |
|---:|---:|:---:|---|---|---|---:|---|

## Kill Order

- P0 (runtime critical): 0
- P1 (planned features): 0
- P2 (cleanup): 0

## Next Iteration Plan (Iter34)

- Proposed focus: fix highest reachable P0/P1 stubs first.
- Suggested touch list:
- Acceptance checks:
  - powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet
  - python -B tools/stubs_kill_list.py --root modules --entry run_ester_fixed.py --out-md docs/stubs_kill_list.md --out-jsonl data/reports/stubs_kill_list.jsonl --top 100
  - python -B tools/stubs_kill_list.py --smoke 1

## Bridges

- Explicit bridge (Ashby): the regulator must know the real system; The priority of edits is set by reachability from the rintite.
- Hidden bridge #1 (Enderton): eksport simvola bez smysla (pass) lomaet dokazuemost kontrakta vyzova.
- Hidden bridge #2 (Carpet&Thomas): ranking by rehabilitation/ref_count reduces the entropy of edits and enhances the useful signal.

## Earth Paragraph

It’s like flaw detection of welds: first we look for cracks on loaded units (rehabilier),
and not on decorative panels. Otherwise, you can polish the “cosmetics” for a long time, and a rupture will happen there,
where pressure and vibration are real (proactivities/agents/rutes).

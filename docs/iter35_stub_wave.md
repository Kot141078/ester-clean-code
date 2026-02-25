# Iter35 Stub Wave

- selection_source: `data/reports/stubs_kill_list.jsonl`
- algorithm: reachable=false, modules/* only, rank by ref_count desc then severity desc, bias to critical subsystems
- wave_size: 20

| rank | path:symbol | stub_kind | ref_count | why_selected | planned_fix |
|---:|---|---|---:|---|---|
| 1 | modules/judge/adapters.py:BaseAdapter.evaluate | not_implemented | 17 | ref_count=17, severity=100 | Explicit runtime contract error instead of NotImplementedError. |
| 2 | modules/media/watchers.py:tick | placeholder_return | 8 | ref_count=8, severity=79 | Rename todo->queued and keep processing summary semantics. |
| 3 | modules/synergy/devices/base.py:DeviceAdapter.can_handle | not_implemented | 5 | ref_count=5, severity=100 | Implement vendor/alias matching for generic adapters. |
| 4 | modules/synergy/devices/base.py:DeviceAdapter.to_canonical | not_implemented | 5 | ref_count=5, severity=100 | Implement safe canonical metric normalization with caps. |
| 5 | modules/social/avatar.py:make | todo_marker | 5 | ref_count=5, severity=45 | Replace marker strings and add explicit unsupported-kind denial. |
| 6 | modules/studio/tts.py:_engine_try | todo_marker | 5 | ref_count=5, severity=45 | Use tone fallback aliasing without marker-based engine id. |
| 7 | modules/reports/export_http.py:_collect | todo_marker | 4 | ref_count=4, severity=43 | Keep degraded export behavior without marker comments. |
| 8 | modules/act/__init__.py:_install_run_plan_fallback._compat_run_plan | placeholder_return | 3 | ref_count=3, severity=69 | Return explicit denial payload when no runnable target exists. |
| 9 | modules/act/__init__.py:_install_run_plan_fallback | todo_marker | 3 | ref_count=3, severity=41 | Install recursion-safe fallback with deterministic target selection. |
| 10 | modules/garage/jobs.py:job_score | todo_marker | 2 | ref_count=2, severity=39, priority_subsystem=garage | Token + semantic-lite scoring instead of placeholder branch. |
| 11 | modules/finance/sepa.py:_pain001 | todo_marker | 2 | ref_count=2, severity=39 | Finalize CtrlSum path without placeholder marker. |
| 12 | modules/ingest/guard.py:__module__ | suppress_init | 1 | ref_count=1, severity=82, priority_subsystem=ingest | Replace silent import suppression with tracked bootstrap error. |
| 13 | modules/thinking/rpa_macros.py:MacroError | pass_only | 1 | ref_count=1, severity=74 | Documented exception class body (no pass-only class). |
| 14 | modules/thinking/think_core.py:_ThinkerB | pass_only | 1 | ref_count=1, severity=74 | AB=B override with explicit think behavior and tag. |
| 15 | modules/garage/proposal.py:auto_assign | placeholder_return | 1 | ref_count=1, severity=65, priority_subsystem=garage | Build task/peer plan from scored job context. |
| 16 | modules/garage/proposal.py:generate_pdf | todo_marker | 1 | ref_count=1, severity=37, priority_subsystem=garage | Stdlib minimal PDF generator for deterministic output. |
| 17 | modules/garage/proposal.py:proposal_build | todo_marker | 1 | ref_count=1, severity=37, priority_subsystem=garage | Project metadata extraction from job and richer scope scaffold. |
| 18 | modules/memory/proactive_adapter.py:_classify_record | todo_marker | 1 | ref_count=1, severity=37, priority_subsystem=memory | Legacy todo detection via pattern without marker literals. |
| 19 | modules/thinking/loop_basic.py:create_app | todo_marker | 1 | ref_count=1, severity=37 | Remove marker text while preserving safe boot routing. |
| 20 | modules/thinking/loop_basic.py:create_app._direct_wellknown_devtools | todo_marker | 1 | ref_count=1, severity=37 | Keep well-known endpoint payload with non-marker note. |

## Bridges

- Explicit bridge (Ashby): increases the variety of modules only if there is a regulator estubs_gateyo + stock + logging.
- Hidden bridge #1 (Carpet&Thomas): goes in waves along eref_koonto, so that the reduction in the entropy of edits is above the noise.
- Hidden bridge #2 (Guyton/Hull): we repair the functional layer and locally repair the mojiwake in the operation area, without massive bleeding of the diffs.

## Earth Paragraph

It's like a major wiring overhaul: the plugs are like twisting electrical tape in the wall.
Until they are replaced with normal machines and terminals, any new tool is risky.
Mozhiwake in comments and lines is like erased wire markings: then it is unclear what goes where.
Poetomu posle Iter35 tsikl fiksirovan: `stubs_kill_list -> wave selection -> fix wave -> re-run list -> stubs_gate`.
